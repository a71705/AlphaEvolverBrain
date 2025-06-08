// src/components/__tests__/NavBar.spec.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { shallowMount, mount } from '@vue/test-utils'; // Import mount for deeper testing if needed
import NavBar from '@/components/NavBar.vue'; // Assumes @ alias is src/

// Mock localStorage for testing authentication status
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn(key => store[key] || null),
    setItem: vi.fn((key, value) => { store[key] = value.toString(); }),
    removeItem: vi.fn(key => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; })
  };
})();

// Define window.localStorage before tests run if not using happy-dom/jsdom's native one
// For happy-dom, it should be available. This is more for jsdom or specific Vitest Node env.
// Object.defineProperty(global, 'localStorage', { value: localStorageMock });
// Vitest with happy-dom usually sets up global.window.localStorage
global.localStorage = localStorageMock;


// Mock Vue Router: useRouter and RouterLink (if needed)
// We need to mock `useRouter` because NavBar setup uses it.
const mockRouterPush = vi.fn();
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router'); // Import actual to ensure other vue-router parts work if needed
  return {
    ...actual, // Spread actual vue-router exports
    useRouter: () => ({ // Mock useRouter
      push: mockRouterPush,
    }),
    // RouterLink: { template: '<a><slot/></a>' } // Basic stub for RouterLink if needed
  };
});

// Mock Element Plus ElMessage (if not globally mocked in setup.js, or for specific spy)
// Assuming ElMessage is globally mocked in setup.js via vi.mock('element-plus', ...)
// If not, individual components might need to mock it or it can be done here too.
// For this test, we'll rely on the global mock if setup.js is configured.

describe('NavBar.vue', () => {
  beforeEach(() => {
    // Reset mocks and localStorage before each test
    localStorageMock.clear();
    mockRouterPush.mockClear();
    // If ElMessage functions were spied on directly (e.g. vi.spyOn(ElMessage, 'success')), clear them:
    // ElMessage.success.mockClear(); // Assuming ElMessage is an object with methods
  });

  it('应正确渲染应用标题', () => {
    const wrapper = shallowMount(NavBar);
    expect(wrapper.find('.app-title').exists()).toBe(true);
    expect(wrapper.find('.app-title').text()).toBe('WorldQuant Brain Alpha 进化系统');
  });

  it('用户未登录时不应显示用户下拉菜单，而是显示“未登录”状态', () => {
    const wrapper = shallowMount(NavBar);
    // Check computed property isLoggedIn directly if possible, or rely on template rendering
    // console.log(wrapper.vm.isLoggedIn); // Accessing computed, only works if not <script setup> or exposed
    expect(wrapper.findComponent({ name: 'ElDropdown' }).exists()).toBe(false); // ElDropdown might not render if v-if="isLoggedIn"
    expect(wrapper.find('.user-status').exists()).toBe(true);
    expect(wrapper.find('.user-status').text()).toBe('未登录');
  });

  it('用户已登录时应显示用户下拉菜单', () => {
    // Simulate logged-in state
    localStorageMock.setItem('session_token', 'mock-token');
    localStorageMock.setItem('expires_at', new Date(Date.now() + 1000 * 60 * 60).toISOString()); // Token expires in 1 hour

    const wrapper = shallowMount(NavBar, {
      global: {
        stubs: { // Stubbing Element Plus components for shallow mount
          'el-dropdown': { template: '<div class="el-dropdown-stub"><slot /><slot name="dropdown" /></div>' },
          'el-dropdown-menu': { template: '<ul class="el-dropdown-menu-stub"><slot /></ul>' },
          'el-dropdown-item': { template: '<li class="el-dropdown-item-stub"><slot /></li>' },
          'el-icon': { template: '<i class="el-icon-stub"></i>' },
          'arrow-down': { template: '<span class="arrow-down-stub"></span>'} // Component name for ArrowDown icon
        }
      }
    });

    expect(wrapper.find('.el-dropdown-stub').exists()).toBe(true);
    expect(wrapper.find('.user-status').exists()).toBe(false); // "未登录" should not be visible
    // Further test: check if "退出登录" item is present
    // This might require deeper mounting or more specific stubs for el-dropdown-item command
  });

  it('点击“退出登录”应清除 localStorage, 显示 ElMessage 成功提示, 并导航到 /login', async () => {
    // Simulate logged-in state
    localStorageMock.setItem('session_token', 'mock-token');
    localStorageMock.setItem('expires_at', new Date(Date.now() + 1000 * 60 * 60).toISOString());

    // For this test, mount might be better to interact with dropdown items,
    // or we directly call the method if it's exposed from setup.
    // Let's assume handleCommand is exposed for testing or called by event.
    const wrapper = shallowMount(NavBar, {
      global: {
        stubs: { // Stub to allow finding the component and its events/props
          'el-dropdown': {
            template: '<div @command="$emit(\'command\', $event)"><slot /><slot name="dropdown" /></div>',
          },
          'el-dropdown-menu': { template: '<ul><slot /></ul>' },
          // For el-dropdown-item, we need to simulate its 'command' prop being part of the event
          'el-dropdown-item': {
            props: ['command'],
            template: '<li @click="$emit(\'click\', command)"><slot /></li>' // Simulate click emitting command
          },
          'el-icon': true,
          'arrow-down': true
        }
      }
    });

    // If handleCommand is exposed via defineExpose in NavBar.vue
    // await wrapper.vm.handleCommand('logout');
    // Or, simulate the event that triggers handleCommand.
    // ElDropdown emits a 'command' event. We need to find el-dropdown and emit it.
    const dropdown = wrapper.findComponent({ name: 'ElDropdown' });
    await dropdown.vm.$emit('command', 'logout'); // Simulate the command event from dropdown

    expect(localStorageMock.getItem('session_token')).toBeNull();
    expect(localStorageMock.getItem('expires_at')).toBeNull();

    // Check ElMessage mock (assuming it's globally mocked or mocked in this file)
    // This requires ElMessage to be available (e.g. from mocked 'element-plus')
    const { ElMessage } = await vi.importActual('element-plus'); // Get the mocked version
    expect(ElMessage.success).toHaveBeenCalledWith('您已成功退出登录');

    expect(mockRouterPush).toHaveBeenCalledWith('/login');
  });
});
