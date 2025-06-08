# app/core/notifications.py
import os
import logging
import yagmail # yagmail 模块
from typing import List, Optional, Any # 确保导入List, Optional, Any

logger = logging.getLogger(__name__)

# 从环境变量获取 SMTP 配置
SMTP_SERVER: Optional[str] = os.environ.get("SMTP_SERVER")
SMTP_PORT_STR: Optional[str] = os.environ.get("SMTP_PORT") # 端口号通常是整数
EMAIL_USERNAME: Optional[str] = os.environ.get("EMAIL_USERNAME")
EMAIL_PASSWORD: Optional[str] = os.environ.get("EMAIL_PASSWORD") # 应用专用密码或API Key

# 邮件发送者地址，如果为空，yagmail 默认使用 EMAIL_USERNAME
NOTIFICATION_EMAIL_SENDER: Optional[str] = os.environ.get("NOTIFICATION_EMAIL_SENDER", EMAIL_USERNAME)
# 默认的测试/通知邮件接收者，可以用于初始化测试
DEFAULT_NOTIFICATION_RECIPIENT: Optional[str] = os.environ.get("DEFAULT_NOTIFICATION_RECIPIENT")


yag_client: Optional[yagmail.SMTP] = None # 类型注解 yagmail.SMTP

def initialize_yagmail() -> None:
    """
    初始化 yagmail SMTP 客户端。
    从环境变量中读取 SMTP 服务器地址、端口、用户名和密码。
    如果配置完整，则创建 yagmail 客户端实例。
    """
    global yag_client # 声明我们要修改全局变量 yag_client

    smtp_port: int = 587 # TLS 的默认端口
    if SMTP_PORT_STR and SMTP_PORT_STR.isdigit():
        smtp_port = int(SMTP_PORT_STR)
    elif SMTP_PORT_STR:
        logger.warning(f"SMTP_PORT 环境变量 '{SMTP_PORT_STR}' 不是有效的数字端口，将使用默认端口 {smtp_port}。")


    if SMTP_SERVER and EMAIL_USERNAME and EMAIL_PASSWORD:
        try:
            # yagmail 会自动处理常见的端口和安全协议 (如 STARTTLS for 587, SSL for 465)
            # 如果 SMTP_PORT 是 465，yagmail 会尝试 SSL，否则默认尝试 STARTTLS
            yag_client = yagmail.SMTP(
                user=EMAIL_USERNAME,
                password=EMAIL_PASSWORD,
                host=SMTP_SERVER,
                port=smtp_port
                # smtp_ssl=(smtp_port == 465) # yagmail 0.11.225 及以后版本似乎会自动处理
            )
            logger.info(f"邮件发送客户端 (yagmail) 初始化成功，连接到服务器 {SMTP_SERVER}:{smtp_port}。")
            # (可选) 初始化后发送测试邮件
            # send_initialization_test_email() # 避免在应用启动时自动发送邮件，除非明确要求
        except Exception as e:
            logger.error(f"初始化 yagmail 客户端失败 (服务器: {SMTP_SERVER}:{smtp_port}): {e}", exc_info=True)
            yag_client = None # 确保初始化失败时客户端为 None
    else:
        logger.warning(
            "SMTP 服务器配置不完整，邮件通知功能将不可用。 "
            "请检查环境变量: SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD。"
        )
        yag_client = None # 确保配置不完整时客户端为 None

def send_email(
    recipient_email: str,
    subject: str,
    body_html: str,
    attachments: Optional[List[str]] = None
) -> bool:
    """
    发送邮件的通用函数。

    参数:
        recipient_email (str): 收件人邮箱地址。
        subject (str): 邮件主题。
        body_html (str): HTML格式的邮件内容。
        attachments (Optional[List[str]]): 附件文件路径列表 (可选)。

    返回:
        bool:邮件是否成功发送。
    """
    global yag_client # 引用全局客户端
    if not yag_client:
        logger.error("邮件客户端未初始化或初始化失败，无法发送邮件。")
        return False

    # 确定发件人地址
    # yagmail 默认使用认证用户 (EMAIL_USERNAME) 作为发件人。
    # 如果 NOTIFICATION_EMAIL_SENDER 设置了且与 EMAIL_USERNAME 不同，
    # 并且邮件服务器允许这种"代表发送"，那么可以尝试使用。
    # 但通常，直接依赖 yagmail 的默认行为（使用认证用户）更可靠。
    # from_addr = NOTIFICATION_EMAIL_SENDER if NOTIFICATION_EMAIL_SENDER and NOTIFICATION_EMAIL_SENDER != EMAIL_USERNAME else None
    # yagmail的 send 方法没有直接的 from_addr 参数，它使用初始化时的用户。
    # 如果需要自定义 From 头部，通常在 yagmail.SMTP 初始化时用 user={'user_email':'display_name'}
    # 或者在发送时，如果yagmail支持，但其API更倾向于使用认证用户作为发件人。

    email_contents: List[Any] = [body_html]
    if attachments:
        email_contents.extend(attachments)

    try:
        yag_client.send(
            to=recipient_email,
            subject=subject,
            contents=email_contents, # HTML内容和附件
        )
        logger.info(f"邮件已成功准备发送至 {recipient_email}，主题: '{subject}'。")
        return True
    except yagmail.errors.YagConnectionClosed as conn_err:
        logger.error(f"发送邮件至 {recipient_email} 失败：Yagmail连接已关闭或无法建立。尝试重新初始化客户端。错误：{conn_err}", exc_info=True)
        # 尝试重新初始化，然后重试一次（可选，简单重试逻辑）
        initialize_yagmail()
        if yag_client:
            try:
                yag_client.send(to=recipient_email, subject=subject, contents=email_contents)
                logger.info(f"重试发送邮件至 {recipient_email} 成功。")
                return True
            except Exception as retry_e:
                logger.error(f"重试发送邮件至 {recipient_email} 仍然失败: {retry_e}", exc_info=True)
                return False
        return False
    except Exception as e:
        logger.error(f"发送邮件至 {recipient_email} 失败: {e}", exc_info=True)
        return False

def send_initialization_test_email() -> None:
    """
    (可选) 在 yagmail 客户端初始化成功后，发送一封测试邮件。
    仅当 DEFAULT_NOTIFICATION_RECIPIENT 环境变量被设置时执行。
    此函数主要用于开发或部署后的手动测试，不建议在应用启动时自动调用。
    """
    if yag_client and DEFAULT_NOTIFICATION_RECIPIENT:
        logger.info(f"尝试发送初始化测试邮件至 {DEFAULT_NOTIFICATION_RECIPIENT}。")
        subject = "WorldQuant Alpha Evolution 系统 - 邮件服务初始化测试"
        body_html = (f"<h1>邮件服务测试</h1>"
                     f"<p>您好,</p>"
                     f"<p>如果您收到此邮件，表明 WorldQuant Alpha Evolution 系统已成功初始化邮件发送服务，"
                     f"并配置为使用用户 {EMAIL_USERNAME} 通过服务器 {SMTP_SERVER}:{SMTP_PORT_STR or '默认端口'} 发送邮件。</p>"
                     f"<p>此邮件为自动发送，请勿回复。</p>"
                     f"<p>祝您使用愉快！</p>")
        if send_email(DEFAULT_NOTIFICATION_RECIPIENT, subject, body_html):
            logger.info(f"初始化测试邮件已成功发送至 {DEFAULT_NOTIFICATION_RECIPIENT}。")
        else:
            logger.error(f"发送初始化测试邮件至 {DEFAULT_NOTIFICATION_RECIPIENT} 失败。")
    elif not DEFAULT_NOTIFICATION_RECIPIENT:
        logger.info("DEFAULT_NOTIFICATION_RECIPIENT 未设置，跳过发送初始化测试邮件。")
    elif not yag_client:
        logger.warning("邮件客户端未初始化，无法发送测试邮件。")

# 注意：实际的应用启动时初始化调用应在 app/main.py 中进行。
# initialize_yagmail() # 不应在此处直接调用，应由应用启动逻辑调用
