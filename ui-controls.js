// UI交互控制和快捷键功能

// 添加键盘快捷键
function addKeyboardShortcuts() {
    // 检查是否已经有事件监听器，避免重复添加
    if (window.shortcutAdded) {
        console.log('快捷键已注册，跳过重复添加');
        return;
    }
    window.shortcutAdded = true;

    // 使用 keydown 事件监听
    document.addEventListener('keydown', handleKeyPress, true);

    console.log('键盘快捷键已注册：Ctrl+Shift+F (批量点击填充)');

    // 显示注册成功状态
    const statusEl = document.getElementById('shortcut-status');
    if (statusEl) {
        statusEl.textContent = '快捷键已启用';
        statusEl.style.color = 'var(--success)';
        setTimeout(() => {
            statusEl.textContent = '';
        }, 3000);
    }
}

// 处理键盘按键
function handleKeyPress(e) {
    e = e || window.event;

    // 检查是否在输入框中
    if (e.target && (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT')) {
        return;
    }

    // 检查是否是 F 键，并满足组合键条件
    const key = e.key.toLowerCase();
    if (key === 'f' && (e.ctrlKey || e.metaKey) && e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        showShortcutFeedback('填充快捷键已触发');
        window.adbControls.batchTapAllFilled();
    }
}

// 显示快捷键反馈
function showShortcutFeedback(message) {
    const statusEl = document.getElementById('shortcut-status');
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.style.color = 'var(--success)';
        setTimeout(() => {
            statusEl.textContent = '';
        }, 2000);
    }
}

// 页面加载完成后添加事件监听器
document.addEventListener('DOMContentLoaded', function () {
    // 点击遮罩层关闭弹窗
    const modalOverlay = document.getElementById('adb-modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function (e) {
            if (e.target === this) {
                window.adbControls.closeAdbModal();
            }
        });
    }

    // ESC 键关闭弹窗
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            window.adbControls.closeAdbModal();
        }
    });
});

// 设置输入框限制
function setupInputFilters() {
    const rowConstraints = document.getElementById('row-constraints');
    const colConstraints = document.getElementById('col-constraints');

    function filterInput(e) {
        const textarea = e.target;
        const cursorPosition = textarea.selectionStart;
        const currentValue = textarea.value;

        // 过滤只保留数字、空格、问号、-1和换行
        const filteredValue = currentValue.replace(/[^0-9?\-\n\s]/g, '');

        // 如果过滤后的值与原值不同，则替换
        if (filteredValue !== currentValue) {
            textarea.value = filteredValue;
            // 恢复光标位置
            const newPosition = cursorPosition - (currentValue.length - filteredValue.length);
            textarea.setSelectionRange(newPosition, newPosition);
        }
    }

    rowConstraints.addEventListener('input', filterInput);
    colConstraints.addEventListener('input', filterInput);
}

// 页面加载时加载配置和设置快捷键
document.addEventListener('DOMContentLoaded', function () {
    window.adbControls.loadConfig();
    setupInputFilters();
    addKeyboardShortcuts();
});

// 导出供其他模块使用
window.uiControls = {
    addKeyboardShortcuts,
    showShortcutFeedback
};