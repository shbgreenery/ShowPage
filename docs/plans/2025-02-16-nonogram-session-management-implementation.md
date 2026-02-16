# 数织游戏会话管理和点击记录功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为数织求解器添加游戏会话管理，避免同一局游戏内重复弹出截图窗口和重复点击格子。

**Architecture:** 通过内存中的会话ID和点击记录集合来跟踪游戏状态，在关键函数中添加检查和更新逻辑。

**Tech Stack:** JavaScript, localStorage (仅用于配置持久化), Set数据结构

---

### Task 1: 添加会话管理数据结构

**Files:**
- Modify: `nonogram.html:740-751`

**Step 1: 添加会话管理变量**

在现有变量后添加：

```javascript
// 游戏会话管理
let gameSession = {
    id: null,              // 会话唯一ID
    hasConfigured: false   // 是否已配置过截图区域
};

// 点击记录管理
let clickedCells = new Set(); // 存储 "row,col" 格式的字符串
```

**Step 2: 添加会话初始化函数**

在脚本中添加新函数：

```javascript
// 初始化游戏会话
function initGameSession() {
    gameSession.id = Date.now().toString();
    gameSession.hasConfigured = false;
    clickedCells.clear();
    console.log('游戏会话已初始化:', gameSession.id);
}
```

**Step 3: 修改页面加载事件**

在 `DOMContentLoaded` 事件监听器中添加：

```javascript
document.addEventListener('DOMContentLoaded', function () {
    loadConfig();
    setupInputFilters();
    initGameSession(); // 初始化游戏会话
});
```

**Step 4: 提交**

```bash
git add nonogram.html
git commit -m "feat: 添加游戏会话管理数据结构和初始化"
```

---

### Task 2: 修改清空函数以重置会话

**Files:**
- Modify: `nonogram.html:1328-1334`

**Step 1: 修改 clearConstraints 函数**

```javascript
function clearConstraints() {
    document.getElementById('row-constraints').value = '';
    document.getElementById('col-constraints').value = '';
    document.getElementById('result-area').classList.remove('show');
    document.getElementById('result-area').innerHTML = '<div style="display: flex; justify-content: center; align-items: center; height: 100%; color: #999; font-style: italic;">结果将显示在这里</div>';
    document.getElementById('status').textContent = '';

    // 重置游戏会话
    initGameSession();
    currentGrid = null;
}
```

**Step 2: 测试验证**

手动测试：
1. 输入约束并求解
2. 点击清空按钮
3. 再次求解应该弹出截图窗口

**Step 3: 提交**

```bash
git add nonogram.html
git commit -m "feat: 清空按钮重置游戏会话"
```

---

### Task 3: 修改求解函数以控制截图窗口

**Files:**
- Modify: `nonogram.html:991-1039`

**Step 1: 修改 solve 函数的截图窗口逻辑**

将 `openScreenshotModal();` 调用替换为：

```javascript
// 求解成功后根据会话状态决定是否弹出截图选择窗口
if (!gameSession.hasConfigured) {
    openScreenshotModal();
} else {
    console.log('使用已配置的截图区域');
}
```

**Step 2: 修改 confirmSelection 函数**

在确认选择后添加：

```javascript
// 标记会话已配置
gameSession.hasConfigured = true;
console.log('截图区域已配置，会话ID:', gameSession.id);
```

**Step 3: 测试验证**

手动测试：
1. 首次求解应弹出截图窗口
2. 再次求解不应弹出截图窗口
3. 清空后再次求解应弹出截图窗口

**Step 4: 提交**

```bash
git add nonogram.html
git commit -m "feat: 根据会话状态控制截图窗口显示"
```

---

### Task 4: 添加点击记录辅助函数

**Files:**
- Modify: `nonogram.html:1358` (在 handleCellClick 函数前)

**Step 1: 添加点击记录辅助函数**

```javascript
// 检查格子是否已点击
function isCellClicked(row, col) {
    return clickedCells.has(`${row},${col}`);
}

// 标记格子为已点击
function markCellClicked(row, col) {
    clickedCells.add(`${row},${col}`);
}

// 清除所有点击记录
function clearClickedCells() {
    clickedCells.clear();
}
```

**Step 2: 提交**

```bash
git add nonogram.html
git commit -m "feat: 添加点击记录辅助函数"
```

---

### Task 5: 修改单个格子点击函数

**Files:**
- Modify: `nonogram.html:1336-1358`

**Step 1: 修改 handleCellClick 函数**

```javascript
// 处理格子点击
async function handleCellClick(row, col, value) {
    // 检查是否已点击
    if (isCellClicked(row, col)) {
        console.log(`格子 (${row + 1}, ${col + 1}) 已点击，跳过`);
        const statusEl = document.getElementById('status');
        statusEl.textContent = `格子 (${row + 1}, ${col + 1}) 已点击`;
        statusEl.className = 'device-connected';
        return;
    }

    // 计算屏幕坐标
    const screenX = adbConfig.startX + col * adbConfig.cellWidth + Math.floor(adbConfig.cellWidth / 2);
    const screenY = adbConfig.startY + row * adbConfig.cellHeight + Math.floor(adbConfig.cellHeight / 2);

    try {
        const statusEl = document.getElementById('status');
        statusEl.textContent = `正在点击格子 (${row + 1}, ${col + 1})...`;
        statusEl.className = 'device-connecting';

        await executeTap(screenX, screenY);

        // 标记为已点击
        markCellClicked(row, col);

        statusEl.textContent = `✓ 已点击格子 (${row + 1}, ${col + 1})`;
        statusEl.className = 'device-connected';

    } catch (error) {
        console.error('点击失败:', error);
        const statusEl = document.getElementById('status');
        statusEl.textContent = `✗ 点击失败: ${error.message}`;
        statusEl.className = 'device-disconnected';
    }
}
```

**Step 2: 测试验证**

手动测试：
1. 求解并配置截图区域
2. 点击某个格子
3. 再次点击同一格子应显示"已点击"提示

**Step 3: 提交**

```bash
git add nonogram.html
git commit -m "feat: 单个格子点击添加重复检查"
```

---

### Task 6: 修改批量点击填充函数

**Files:**
- Modify: `nonogram.html:865-926`

**Step 1: 修改 batchTapAllFilled 函数**

```javascript
// 批量点击所有填充格子
async function batchTapAllFilled() {
    const statusEl = document.getElementById('status');
    const batchBtn = document.getElementById('batch-tap-btn');

    if (!currentGrid) {
        alert('点击填充前，请先求解数织！');
        return;
    }

    // 收集所有填充格子
    const allFilledCells = [];
    for (let r = 0; r < currentGrid.length; r++) {
        for (let c = 0; c < currentGrid[r].length; c++) {
            if (currentGrid[r][c] === FILLED) {
                const screenX = adbConfig.startX + c * adbConfig.cellWidth + Math.floor(adbConfig.cellWidth / 2);
                const screenY = adbConfig.startY + r * adbConfig.cellHeight + Math.floor(adbConfig.cellHeight / 2);
                allFilledCells.push({
                    x: screenX,
                    y: screenY,
                    row: r,
                    col: c
                });
            }
        }
    }

    // 过滤掉已点击的格子
    const newFilledCells = allFilledCells.filter(cell => !isCellClicked(cell.row, cell.col));
    const skippedCount = allFilledCells.length - newFilledCells.length;

    if (newFilledCells.length === 0) {
        alert(skippedCount > 0 ? `所有填充格子都已点击！` : '没有填充的格子！');
        return;
    }

    // 确认操作
    const confirmMsg = skippedCount > 0
        ? `准备批量点击 ${newFilledCells.length} 个填充格子（跳过 ${skippedCount} 个已点击），确定继续吗？`
        : `准备批量点击 ${newFilledCells.length} 个填充格子，确定继续吗？`;

    if (!confirm(confirmMsg)) {
        return;
    }

    // 禁用按钮
    batchBtn.disabled = true;
    batchBtn.textContent = '点击中...';

    statusEl.textContent = `正在批量点击 ${newFilledCells.length} 个填充格子...`;
    statusEl.className = 'device-connecting';

    try {
        const result = await executeTap(newFilledCells);

        // 标记成功点击的格子
        newFilledCells.forEach(cell => {
            markCellClicked(cell.row, cell.col);
        });

        // 恢复状态
        batchBtn.disabled = false;
        batchBtn.textContent = '点击填充';

        if (result.failed === 0) {
            const msg = skippedCount > 0
                ? `✓ 批量点击完成！成功 ${result.success} 个（跳过 ${skippedCount} 个已点击）`
                : `✓ 批量点击完成！成功 ${result.success} 个`;
            statusEl.textContent = msg;
            statusEl.className = 'device-connected';
        } else {
            statusEl.textContent = `⚠ 批量点击完成！成功 ${result.success} 个，失败 ${result.failed} 个`;
            statusEl.className = 'device-disconnected';
        }

    } catch (error) {
        console.error('批量点击失败:', error);
        batchBtn.disabled = false;
        batchBtn.textContent = '点击填充';
        statusEl.textContent = `✗ 批量点击失败: ${error.message}`;
        statusEl.className = 'device-disconnected';
    }
}
```

**Step 2: 提交**

```bash
git add nonogram.html
git commit -m "feat: 批量点击填充添加重复检查和记录"
```

---

### Task 7: 修改批量点击空格函数

**Files:**
- Modify: `nonogram.html:928-989`

**Step 1: 修改 batchTapAllEmpty 函数**

类似批量点击填充的修改，将 FILLED 改为 EMPTY：

```javascript
// 批量点击所有空格子
async function batchTapAllEmpty() {
    const statusEl = document.getElementById('status');
    const batchBtn = document.getElementById('batch-tap-empty-btn');

    if (!currentGrid) {
        alert('点击空格前，请先求解数织！');
        return;
    }

    // 收集所有空格子
    const allEmptyCells = [];
    for (let r = 0; r < currentGrid.length; r++) {
        for (let c = 0; c < currentGrid[r].length; c++) {
            if (currentGrid[r][c] === EMPTY) {
                const screenX = adbConfig.startX + c * adbConfig.cellWidth + Math.floor(adbConfig.cellWidth / 2);
                const screenY = adbConfig.startY + r * adbConfig.cellHeight + Math.floor(adbConfig.cellHeight / 2);
                allEmptyCells.push({
                    x: screenX,
                    y: screenY,
                    row: r,
                    col: c
                });
            }
        }
    }

    // 过滤掉已点击的格子
    const newEmptyCells = allEmptyCells.filter(cell => !isCellClicked(cell.row, cell.col));
    const skippedCount = allEmptyCells.length - newEmptyCells.length;

    if (newEmptyCells.length === 0) {
        alert(skippedCount > 0 ? `所有空格子都已点击！` : '没有空格子！');
        return;
    }

    // 确认操作
    const confirmMsg = skippedCount > 0
        ? `准备批量点击 ${newEmptyCells.length} 个空格子（跳过 ${skippedCount} 个已点击），确定继续吗？`
        : `准备批量点击 ${newEmptyCells.length} 个空格子，确定继续吗？`;

    if (!confirm(confirmMsg)) {
        return;
    }

    // 禁用按钮
    batchBtn.disabled = true;
    batchBtn.textContent = '点击中...';

    statusEl.textContent = `正在批量点击 ${newEmptyCells.length} 个空格子...`;
    statusEl.className = 'device-connecting';

    try {
        const result = await executeTap(newEmptyCells);

        // 标记成功点击的格子
        newEmptyCells.forEach(cell => {
            markCellClicked(cell.row, cell.col);
        });

        // 恢复状态
        batchBtn.disabled = false;
        batchBtn.textContent = '点击空格';

        if (result.failed === 0) {
            const msg = skippedCount > 0
                ? `✓ 批量点击完成！成功 ${result.success} 个（跳过 ${skippedCount} 个已点击）`
                : `✓ 批量点击完成！成功 ${result.success} 个`;
            statusEl.textContent = msg;
            statusEl.className = 'device-connected';
        } else {
            statusEl.textContent = `⚠ 批量点击完成！成功 ${result.success} 个，失败 ${result.failed} 个`;
            statusEl.className = 'device-disconnected';
        }

    } catch (error) {
        console.error('批量点击失败:', error);
        batchBtn.disabled = false;
        batchBtn.textContent = '点击空格';
        statusEl.textContent = `✗ 批量点击失败: ${error.message}`;
        statusEl.className = 'device-disconnected';
    }
}
```

**Step 2: 测试验证**

完整测试流程：
1. 输入约束并求解
2. 配置截图区域
3. 批量点击填充
4. 再次批量点击填充应显示跳过数量
5. 单击某个已点击的格子应显示提示
6. 点击清空重置会话
7. 重新求解应重新弹出截图窗口

**Step 3: 提交**

```bash
git add nonogram.html
git commit -m "feat: 批量点击空格添加重复检查和记录"
```

---

### Task 8: 最终测试和优化

**Files:**
- Modify: `nonogram.html`

**Step 1: 添加调试日志**

在关键位置添加日志以便调试：

```javascript
// 在 initGameSession 中
console.log('游戏会话初始化:', gameSession.id);

// 在 solve 函数中
if (!gameSession.hasConfigured) {
    console.log('首次配置截图区域');
    openScreenshotModal();
} else {
    console.log('使用已配置的截图区域，会话ID:', gameSession.id);
}

// 在 confirmSelection 中
gameSession.hasConfigured = true;
console.log('截图区域已配置，会话ID:', gameSession.id);
```

**Step 2: 完整功能测试**

测试场景：
1. 页面刷新 → 新会话
2. 求解 → 弹出截图窗口
3. 再次求解 → 不弹窗
4. 批量点击 → 记录点击状态
5. 重复批量点击 → 跳过已点击
6. 清空 → 重置会话
7. 重新求解 → 弹出截图窗口

**Step 3: 提交最终版本**

```bash
git add nonogram.html
git commit -m "feat: 完成游戏会话管理和点击记录功能"
```

---

## 实现总结

该功能实现了：
1. 游戏会话管理，区分不同游戏局
2. 截图窗口按会话控制显示
3. 点击记录避免重复点击
4. 批量点击优化，提升效率
5. 清晰的状态反馈

所有功能都在内存中实现，无需持久化存储，符合用户需求。