// src/tests/setup.js
import { vi } from 'vitest'; // Vitest's mocking utilities

// 全局 Mock Element Plus 组件或方法 (示例)
// 如果在很多测试中都需要 mock 相同的 Element Plus 组件，可以在这里进行全局 mock。
// 例如，mock ElMessage 以避免在测试过程中实际弹出消息提示。
vi.mock('element-plus', async (importOriginal) => {
  const original = await importOriginal(); // 获取原始模块
  return {
    ...original, // 保留原始模块的其他导出
    ElMessage: { // Mock ElMessage 对象
      success: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
      error: vi.fn(),
    },
    // ElNotification: { ...vi.fn() }, // 如果用到 ElNotification 也类似处理
    // ElLoading: { service: vi.fn(() => ({ close: vi.fn() }))}, // 如果用到 ElLoading 服务
  };
});

// Mock localStorage (如果测试需要操作localStorage且运行环境可能没有完全实现)
// Vitest 的 happy-dom 或 jsdom 环境通常提供了 localStorage 的实现。
// 但如果遇到问题或需要特定行为，可以像下面这样mock：
/*
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => { store[key] = value.toString(); },
    removeItem: (key) => { delete store[key]; },
    clear: () => { store = {}; },
    key: (index) => Object.keys(store)[index] || null,
    get length() {
      return Object.keys(store).length;
    }
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });
Object.defineProperty(global, 'localStorage', { value: localStorageMock }); // 如果在Node环境的测试中也需要
*/

// Mock Canvas API for Chart.js (如果 happy-dom/jsdom 支持不足)
// Vitest + happy-dom 通常对 Canvas 有一些基本支持。
// 如果 Chart.js 报错，可能需要更完善的 Canvas mock。
// 一个非常基础的 mock 如下，仅防止 getContext('2d') 调用失败：
if (typeof HTMLCanvasElement !== 'undefined') {
  HTMLCanvasElement.prototype.getContext = function getContext(contextId) {
    if (contextId === '2d') {
      // 返回一个极简的 mock 2D 上下文对象
      return {
        fillRect: vi.fn(),
        clearRect: vi.fn(),
        getImageData: vi.fn((x, y, sw, sh) => ({ data: new Uint8ClampedArray(sw * sh * 4) })),
        putImageData: vi.fn(),
        createImageData: vi.fn(() => ({ data: new Uint8ClampedArray(0) })),
        setTransform: vi.fn(),
        drawImage: vi.fn(),
        save: vi.fn(),
        fillText: vi.fn(),
        restore: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        closePath: vi.fn(),
        stroke: vi.fn(),
        strokeRect: vi.fn(),
        measureText: vi.fn(() => ({ width: 0 })),
        transform: vi.fn(),
        translate: vi.fn(),
        scale: vi.fn(),
        rotate: vi.fn(),
        arc: vi.fn(),
        fill: vi.fn(),
        // 添加 Chart.js 可能调用的其他 Canvas API 方法的 mock 实现
      };
    }
    return null; // 其他上下文类型返回 null
  };
}

// 清理 mocks (如果需要全局的 beforeEach/afterEach 行为)
// import { beforeEach } from 'vitest'
// beforeEach(() => {
//   localStorageMock.clear();
//   vi.clearAllMocks(); // 清除所有 vi.fn() 的调用记录等
// });

// 全局 Vue Test Utils 配置 (可选)
// import { config } from '@vue/test-utils';
// config.global.plugins = [ ... ];
// config.global.components = { ... };
// config.global.directives = { ... };
// config.global.stubs = { // 全局存根
//   'el-button': true, // 将所有 el-button 存根掉
//   'router-link': RouterLinkStub // 使用 RouterLinkStub 存根 router-link
// };

logger.info("Vitest setup file loaded: mocks for ElementPlus.ElMessage and basic Canvas API applied.");
console.log("Vitest global setup (setup.js): ElMessage mocked, basic Canvas API mocked.");

// 可以在这里添加更多全局的测试配置或 mock
