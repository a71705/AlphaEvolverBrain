// src/components/AlphaStructureViewer.vue
<template>
  <div class="alpha-structure-viewer">
    <pre v-if="treeDataFormatted" class="structure-code"><code v-html="treeDataFormatted"></code></pre>
    <el-empty v-else :description="emptyDescription"></el-empty>
  </div>
</template>

<script>
import { computed } from 'vue';
import { ElEmpty } from 'element-plus';

export default {
  name: 'AlphaStructureViewer',
  components: { ElEmpty },
  props: {
    treeData: { // 预期格式: { value: string, children?: Array<TreeData> }
      type: Object,
      default: null,
    },
  },
  setup(props) {
    // HTML转义函数，防止XSS（虽然这里是内部数据，但良好实践）
    const escapeHtml = (unsafe) => {
        if (unsafe === null || unsafe === undefined) return '';
        return String(unsafe) // Ensure it's a string before replacing
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    };

    // 递归函数，将树节点JSON对象转换为带缩进的HTML字符串
    const formatNodeToHtml = (node, indentLevel = 0) => {
      if (!node || typeof node.value === 'undefined') {
        // console.warn("formatNodeToHtml: 无效节点或无value属性", node);
        return '';
      }

      const indentSize = 4; // 每个层级的缩进空格数 (用4个nbsp更明显)
      const currentIndent = '&nbsp;'.repeat(indentLevel * indentSize);

      // 根据节点是否有子节点来决定前缀和样式
      const hasChildren = node.children && Array.isArray(node.children) && node.children.length > 0;
      const nodeTypeClass = hasChildren ? 'node-operator' : 'node-leaf';
      const prefixSymbol = hasChildren ? '&#9660;' : '&#9679;'; // ▼ for operator, ● for leaf

      let htmlString = `${currentIndent}<span class="${nodeTypeClass}">${prefixSymbol} ${escapeHtml(node.value)}</span><br>`;

      if (hasChildren) {
        for (const child of node.children) {
          // 确保child也是有效对象才进行递归
          if (child && typeof child.value !== 'undefined') {
            htmlString += formatNodeToHtml(child, indentLevel + 1);
          } else if (child) { // 如果child存在但格式不对 (例如, 不是对象或没有value)
            htmlString += `${'&nbsp;'.repeat((indentLevel + 1) * indentSize)}<span class="node-error">[无效子节点数据]</span><br>`;
          }
        }
      }
      return htmlString;
    };

    const treeDataFormatted = computed(() => {
      if (props.treeData && Object.keys(props.treeData).length > 0) { // 检查treeData是否非空对象
        try {
          return formatNodeToHtml(props.treeData);
        } catch (e) {
          console.error("格式化树结构JSON时出错:", e);
          return `<span class="node-error">错误：无法渲染树结构 (${escapeHtml(e.message)})</span>`;
        }
      }
      return null;
    });

    const emptyDescription = computed(() => {
        if (!props.treeData) return "无表达式结构数据或后端未提供。";
        if (Object.keys(props.treeData).length === 0) return "表达式结构数据为空对象。";
        return "无法生成树形结构，请检查数据格式。"; // 针对 treeDataFormatted 为 null 但 treeData 有内容的情况
    });


    return {
      treeDataFormatted,
      emptyDescription,
    };
  },
};
</script>

<style scoped>
.alpha-structure-viewer {
  background-color: #fdfdfd; /* 更淡的背景 */
  padding: 15px 20px; /* 调整内边距 */
  border-radius: 4px;
  border: 1px solid #ebeef5; /* Element Plus 边框颜色 */
  max-height: 450px; /* 增加最大高度 */
  overflow-y: auto;
  text-align: left;
  box-shadow: 0 0 5px rgba(0,0,0,0.05); /* 轻微阴影 */
}
.alpha-structure-viewer pre.structure-code { /* 给pre标签特定类名 */
  margin: 0;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
  font-size: 13px; /* 调整字体大小 */
  line-height: 1.6; /* 调整行高 */
}
/* code 标签通常由 pre 继承字体，但可以明确设置 */
.alpha-structure-viewer code {
  white-space: pre;
  display: block; /* 确保 code 块级显示以应用 pre 的滚动 */
}

/* 在 <style scoped> 中定义全局可用的类，如果 v-html 中的 span 想用它们 */
/* 或者将这些样式放到全局 CSS 中，或者在 formatNodeToHtml 中使用内联样式 */
/* 全局样式 (如果 formatNodeToHtml 中的 class 要生效，不能在 scoped 中定义，除非使用 :deep() 或 ::v-deep) */
</style>
<style>
/* 非 scoped 样式，以便 v-html 中的 class 可以应用 */
.alpha-structure-viewer .node-operator {
  font-weight: bold;
  color: #409EFF; /* Element Plus 主题蓝 */
}
.alpha-structure-viewer .node-leaf {
  color: #67C23A; /* Element Plus 成功绿 */
}
.alpha-structure-viewer .node-error {
  color: #F56C6C; /* Element Plus 危险红 */
  font-style: italic;
}
</style>
