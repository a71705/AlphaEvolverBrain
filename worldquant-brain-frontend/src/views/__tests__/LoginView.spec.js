// src/views/__tests__/LoginView.spec.js
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mount } from '@vue/test-utils'; // Using mount for form interactions
import LoginView from '@/views/LoginView.vue';
import axios from 'axios'; // Will be mocked by axios-mock-adapter
import MockAdapter from 'axios-mock-adapter';
// Assuming ElMessage, ElForm, etc. are globally stubbed or available in test env
// or individually mocked if needed. setup.js handles ElMessage.

// Mock Vue Router
const mockRouterPush = vi.fn();
vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router');
  return {
    ...actual,
    useRouter: () => ({
      push: mockRouterPush,
    }),
  };
});

// Mock localStorage (same as in NavBar.spec.js)
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn(key => store[key] || null),
    setItem: vi.fn((key, value) => { store[key] = value.toString(); }),
    removeItem: vi.fn(key => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; })
  };
})();
global.localStorage = localStorageMock;


describe('LoginView.vue', () => {
  let mockAxios;

  beforeEach(() => {
    // Create a new MockAdapter instance before each test
    mockAxios = new MockAdapter(axios);
    localStorageMock.clear();
    mockRouterPush.mockClear();
    // vi.clearAllMocks(); // If other global mocks need clearing
  });

  afterEach(() => {
    // Restore axios to its original state after each test
    mockAxios.restore();
  });

  it('应正确渲染登录表单，包含邮箱、密码输入框和登录按钮', () => {
    const wrapper = mount(LoginView, {
      global: {
        stubs: { // Stubbing Element Plus components for stability and focus
          'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
          'el-form': { template: '<form @submit.prevent="$emit(\'submit\')"><slot /></form>' }, // Simulate form submission
          'el-form-item': { template: '<div><slot name="label" /><slot /></div>' },
          'el-input': {
            props: ['modelValue', 'type', 'placeholder', 'showPassword'],
            template: '<input :type="type || \'text\'" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" :placeholder="placeholder" />',
            emits: ['update:modelValue']
          },
          'el-button': { template: '<button :type="$attrs.type || \'button\'"><slot /></button>' },
          'el-alert': { template: '<div class="el-alert-stub"><slot name="title" /></div>', props: ['title', 'type', 'showIcon', 'closable'] },
          'el-icon': true, // Basic stub for any icons used internally by ElInput (like show-password)
        }
      }
    });

    expect(wrapper.find('input[placeholder="请输入邮箱"]').exists()).toBe(true);
    // For password, due to Element Plus's internal structure for show-password,
    // we might need to be less specific or use a more complex selector.
    // This simple input selector works if el-input is stubbed as above.
    expect(wrapper.find('input[type="password"]').exists()).toBe(true);
    expect(wrapper.find('button').text()).toContain('登录');
  });

  it('输入有效凭据并提交后，应成功登录、存储token并跳转到/experiments', async () => {
    const tokenData = {
      session_token: 'mock-session-token-123',
      expires_at: new Date(Date.now() + 3600 * 1000).toISOString() // Expires in 1 hour
    };
    // Mock the API call for login
    // The URL might depend on VUE_APP_API_BASE_URL, ensure it's consistent or mock process.env
    mockAxios.onPost('/api/v1/auth/login').reply(200, tokenData);

    const wrapper = mount(LoginView, { /* stubs as above or remove for full mount */ });

    // Simulate user input
    await wrapper.find('input[placeholder="请输入邮箱"]').setValue('test@example.com');
    await wrapper.find('input[type="password"]').setValue('correctPassword123');

    // Simulate form submission
    await wrapper.find('form').trigger('submit.prevent');

    // Wait for promise in handleLogin to resolve and DOM updates
    // Vitest typically handles promises well, but an explicit await for microtasks can be useful.
    await new Promise(resolve => setTimeout(resolve, 0)); // Or await wrapper.vm.$nextTick() for Vue specific updates

    expect(localStorageMock.setItem).toHaveBeenCalledWith('session_token', tokenData.session_token);
    expect(localStorageMock.setItem).toHaveBeenCalledWith('expires_at', tokenData.expires_at);
    expect(mockRouterPush).toHaveBeenCalledWith('/experiments');
  });

  it('输入无效邮箱格式时，应显示表单验证错误', async () => {
    const wrapper = mount(LoginView); // Full mount to test Element Plus validation

    await wrapper.find('input[placeholder="请输入邮箱"]').setValue('invalid-email');
    await wrapper.find('input[type="password"]').setValue('password123');

    // Trigger validation by attempting to submit or by blurring the field
    // Element Plus form validation might trigger on blur or submit.
    // For this test, clicking the submit button is more direct.
    await wrapper.find('button[type="primary"]').trigger('click');

    await wrapper.vm.$nextTick(); // Wait for Vue to update DOM with validation messages

    // Check for Element Plus validation error message
    // This depends on how ElFormItem displays errors. Usually a div with class 'el-form-item__error'
    const errorMessages = wrapper.findAll('.el-form-item__error');
    expect(errorMessages.some(msg => msg.text().includes('请输入正确的邮箱地址'))).toBe(true);
  });

  it('登录API调用失败时，应显示错误提示 (el-alert)', async () => {
    mockAxios.onPost('/api/v1/auth/login').reply(401, { detail: "认证失败，凭据无效" });

    const wrapper = mount(LoginView, { /* stubs */ });

    await wrapper.find('input[placeholder="请输入邮箱"]').setValue('user@example.com');
    await wrapper.find('input[type="password"]').setValue('wrongpassword');
    await wrapper.find('form').trigger('submit.prevent');

    await new Promise(resolve => setTimeout(resolve, 0)); // Wait for async operations
    await wrapper.vm.$nextTick();

    const alert = wrapper.findComponent({ name: 'ElAlert' }); // Find ElAlert component
    expect(alert.exists()).toBe(true);
    expect(alert.props('title')).toContain("登录失败：认证失败，凭据无效");
    expect(alert.props('type')).toBe('error');
  });

  // TODO:
  // - Test password field validation (e.g., minimum length).
  // - Test login attempt when API returns a 500 server error.
  // - Test login attempt when network error occurs.
  // - Test loading state (button should be disabled/show loading spinner).
});
