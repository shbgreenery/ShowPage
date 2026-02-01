// ADB相关功能和控制

// ADB 配置
let adbConfig = {
    startX: 180,
    startY: 890,
    cellWidth: 62,
    cellHeight: 62,
    whiteThreshold: 240  // 白色阈值（后端使用精确值：R>=235, G>=235, B>=210）
};

// 代理服务器相关变量
let proxyConnected = false;
let proxyUrl = 'http://localhost:8085';

// 废弃的 WebUSB 变量（保持兼容性）
let adbConnected = false;
let adbDevice = null;

// 保存配置到 localStorage
function saveConfig() {
    proxyUrl = document.getElementById('proxy-url').value;
    localStorage.setItem('proxyUrl', proxyUrl);
}

// 从 localStorage 加载配置
function loadConfig() {
    const savedProxyUrl = localStorage.getItem('proxyUrl');
    if (savedProxyUrl) {
        proxyUrl = savedProxyUrl;
        document.getElementById('proxy-url').value = proxyUrl;
    }
}

// 测试代理服务器连接
async function testProxyConnection() {
    const statusEl = document.getElementById('status');
    const deviceStatusEl = document.getElementById('device-status');
    const testBtn = document.getElementById('test-btn');
    proxyUrl = document.getElementById('proxy-url').value;

    try {
        statusEl.textContent = '正在测试连接...';
        deviceStatusEl.textContent = '正在测试连接...';
        statusEl.className = 'device-connecting';
        deviceStatusEl.className = 'device-connecting';
        testBtn.disabled = true;

        // 测试健康检查
        const healthResponse = await fetch(`${proxyUrl}/health`, {
            method: 'GET',
            mode: 'cors'
        });

        if (!healthResponse.ok) {
            throw new Error('代理服务器响应异常');
        }

        const healthData = await healthResponse.json();

        // 获取设备列表
        const devicesResponse = await fetch(`${proxyUrl}/devices`, {
            method: 'GET',
            mode: 'cors'
        });

        if (!devicesResponse.ok) {
            throw new Error('获取设备列表失败');
        }

        const devicesData = await devicesResponse.json();

        if (devicesData.devices.length === 0) {
            throw new Error('未检测到已连接的设备，请确保手机已连接并开启 USB 调试');
        }

        proxyConnected = true;
        const deviceInfo = devicesData.devices[0];
        statusEl.textContent = `✓ 设备已连接: ${deviceInfo.serial} (${deviceInfo.status})`;
        deviceStatusEl.textContent = `✓ 已连接: ${deviceInfo.serial} (${deviceInfo.status})`;
        statusEl.className = 'device-connected';
        deviceStatusEl.className = 'device-connected';

    } catch (error) {
        console.error('连接失败:', error);
        proxyConnected = false;

        let errorMsg = error.message;
        if (error.name === 'TypeError' && errorMsg.includes('Failed to fetch')) {
            errorMsg = '无法连接到代理服务器。请确保：\n1. 已运行 python3 adb_proxy.py\n2. 代理服务器地址正确';
        }

        statusEl.textContent = `✗ 连接失败: ${errorMsg}`;
        deviceStatusEl.textContent = `✗ 连接失败: ${errorMsg}`;
        statusEl.className = 'device-disconnected';
        deviceStatusEl.className = 'device-disconnected';
    } finally {
        testBtn.disabled = false;
    }
}

// 检测指定位置的颜色
async function getColorAt(x, y) {
    if (!proxyConnected) {
        throw new Error('代理服务器未连接，请先点击"测试连接"');
    }

    try {
        const response = await fetch(`${proxyUrl}/get-color`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ x, y, white_threshold: adbConfig.whiteThreshold })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || '颜色检测失败');
        }

        const result = await response.json();
        return result;
    } catch (error) {
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            proxyConnected = false;
            const statusEl = document.getElementById('status');
            const deviceStatusEl = document.getElementById('device-status');
            statusEl.textContent = '⚠ 代理服务器连接中断';
            deviceStatusEl.textContent = '⚠ 代理服务器连接中断';
            statusEl.className = 'device-disconnected';
            deviceStatusEl.className = 'device-disconnected';
        }
        // 颜色检测失败时，返回默认的白色结果，确保点击操作继续
        console.warn(`颜色检测失败 (${x}, ${y}): ${error.message}，默认执行点击`);
        return {
            status: 'ok',
            x: x,
            y: y,
            color: { r: 255, g: 255, b: 255 },
            is_white: true
        };
    }
}

// 批量检测多个位置的颜色（性能优化）
async function getColorsBatch(positions) {
    if (!proxyConnected) {
        throw new Error('代理服务器未连接，请先点击"测试连接"');
    }

    try {
        const response = await fetch(`${proxyUrl}/get-color`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ positions, white_threshold: adbConfig.whiteThreshold })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || '批量颜色检测失败');
        }

        const result = await response.json();
        return result.results;
    } catch (error) {
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            proxyConnected = false;
            const statusEl = document.getElementById('status');
            const deviceStatusEl = document.getElementById('device-status');
            statusEl.textContent = '⚠ 代理服务器连接中断';
            deviceStatusEl.textContent = '⚠ 代理服务器连接中断';
            statusEl.className = 'device-disconnected';
            deviceStatusEl.className = 'device-disconnected';
        }
        // 批量检测失败时，返回默认的白色结果
        console.warn(`批量颜色检测失败: ${error.message}，默认全部点击`);
        return positions.map(pos => ({
            status: 'ok',
            x: pos.x,
            y: pos.y,
            color: { r: 255, g: 255, b: 255 },
            is_white: true
        }));
    }
}

// 通过代理执行点击命令
async function executeTap(x, y) {
    if (!proxyConnected) {
        throw new Error('代理服务器未连接，请先点击"测试连接"');
    }

    const command = `input tap ${x} ${y}`;

    try {
        const response = await fetch(`${proxyUrl}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ command })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || '命令执行失败');
        }
        const result = await response.json();
        if (result.returncode !== 0) {
            throw new Error(`命令执行失败: ${result.stderr || result.stdout}`);
        }
        return result;
    } catch (error) {
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            proxyConnected = false;
            const statusEl = document.getElementById('status');
            const deviceStatusEl = document.getElementById('device-status');
            statusEl.textContent = '⚠ 代理服务器连接中断';
            deviceStatusEl.textContent = '⚠ 代理服务器连接中断';
            statusEl.className = 'device-disconnected';
            deviceStatusEl.className = 'device-disconnected';
        }
        throw error;
    }
}

// 批量点击所有填充格子
async function batchTapAllFilled() {
    const statusEl = document.getElementById('status');
    const deviceStatusEl = document.getElementById('device-status');
    const batchBtn = document.getElementById('batch-tap-btn');

    if (!window.nonogramCore.currentGrid) {
        alert('点击填充前，请先求解数织！');
        return;
    }

    if (!proxyConnected) {
        alert('请先点击"测试连接"！');
        return;
    }

    // 收集所有填充格子的坐标
    const filledCells = [];
    for (let r = 0; r < window.nonogramCore.currentGrid.length; r++) {
        for (let c = 0; c < window.nonogramCore.currentGrid[r].length; c++) {
            if (window.nonogramCore.currentGrid[r][c] === window.nonogramCore.FILLED) {
                const screenX = adbConfig.startX + c * adbConfig.cellWidth + Math.floor(adbConfig.cellWidth / 2);
                const screenY = adbConfig.startY + r * adbConfig.cellHeight + Math.floor(adbConfig.cellHeight / 2);
                filledCells.push({ row: r, col: c, x: screenX, y: screenY });
            }
        }
    }

    if (filledCells.length === 0) {
        alert('没有填充的格子！');
        return;
    }

    // 确认操作
    if (!confirm(`准备批量点击 ${filledCells.length} 个填充格子，确定继续吗？`)) {
        return;
    }

    // 禁用按钮
    batchBtn.disabled = true;
    batchBtn.textContent = '点击中...';

    let successCount = 0;
    let failCount = 0;

    // 性能优化：批量检测所有格子的颜色
    statusEl.textContent = `正在批量检测 ${filledCells.length} 个格子的颜色...`;
    deviceStatusEl.textContent = `批量颜色检测中...`;
    statusEl.className = 'device-connecting';
    deviceStatusEl.className = 'device-connecting';

    try {
        // 准备批量检测的位置数据
        const positions = filledCells.map(cell => ({ x: cell.x, y: cell.y }));

        // 批量检测颜色（只截图一次）
        const colorResults = await getColorsBatch(positions);

        console.log(`批量颜色检测完成，共检测 ${colorResults.length} 个位置`);

        // 执行点击操作
        for (let i = 0; i < filledCells.length; i++) {
            const cell = filledCells[i];
            const colorResult = colorResults[i];

            statusEl.textContent = `正在点击填充格子 (${cell.row + 1}, ${cell.col + 1})... (${i + 1}/${filledCells.length})`;
            deviceStatusEl.textContent = `正在点击 (${cell.row + 1}, ${cell.col + 1})... (${i + 1}/${filledCells.length})`;

            try {
                if (colorResult.is_white) {
                    // 只有白色位置才点击
                    await executeTap(cell.x, cell.y);
                    successCount++;
                } else {
                    console.log(`跳过已填充的格子 (${cell.row + 1}, ${cell.col + 1})，颜色: RGB(${colorResult.color.r}, ${colorResult.color.g}, ${colorResult.color.b})`);
                    successCount++; // 算作成功处理，因为已经填充
                }

                // 添加小延迟，避免点击过快
                await new Promise(resolve => setTimeout(resolve, 50)); // 减少延迟，因为颜色检测已经完成
            } catch (error) {
                console.error(`点击 (${cell.row + 1}, ${cell.col + 1}) 失败:`, error);
                failCount++;
            }
        }
    } catch (error) {
        console.error('批量颜色检测失败，回退到逐个检测模式:', error);

        // 回退到原来的逐个检测模式
        for (let i = 0; i < filledCells.length; i++) {
            const cell = filledCells[i];
            statusEl.textContent = `正在点击填充格子 (${cell.row + 1}, ${cell.col + 1})... (${i + 1}/${filledCells.length})`;
            deviceStatusEl.textContent = `正在点击 (${cell.row + 1}, ${cell.col + 1})... (${i + 1}/${filledCells.length})`;

            try {
                // 检查颜色
                const colorResult = await getColorAt(cell.x, cell.y);

                if (colorResult.is_white) {
                    // 只有白色位置才点击
                    await executeTap(cell.x, cell.y);
                    successCount++;
                } else {
                    console.log(`跳过已填充的格子 (${cell.row + 1}, ${cell.col + 1})，颜色: RGB(${colorResult.color.r}, ${colorResult.color.g}, ${colorResult.color.b})`);
                    successCount++; // 算作成功处理，因为已经填充
                }

                // 添加小延迟，避免操作过快
                await new Promise(resolve => setTimeout(resolve, 100));
            } catch (error) {
                console.error(`处理 (${cell.row + 1}, ${cell.col + 1}) 失败:`, error);
                failCount++;
            }
        }
    }

    // 恢复状态
    batchBtn.disabled = false;
    batchBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" fill="currentColor"/></svg> 点击填充格';

    if (failCount === 0) {
        statusEl.textContent = `✓ 批量点击填充完成！成功 ${successCount} 个`;
        deviceStatusEl.textContent = `✓ 批量点击完成！成功 ${successCount} 个`;
        statusEl.className = 'device-connected';
        deviceStatusEl.className = 'device-connected';
    } else {
        statusEl.textContent = `⚠ 批量点击填充完成！成功 ${successCount} 个，失败 ${failCount} 个`;
        deviceStatusEl.textContent = `⚠ 批量点击完成！成功 ${successCount} 个，失败 ${failCount} 个`;
        statusEl.className = 'device-disconnected';
        deviceStatusEl.className = 'device-disconnected';
    }

    // 3秒后恢复状态
    setTimeout(() => {
        if (proxyConnected) {
            statusEl.textContent = `✓ 设备已连接，可以点击格子进行操作`;
            deviceStatusEl.textContent = `✓ 代理已连接`;
            statusEl.className = 'device-connected';
            deviceStatusEl.className = 'device-connected';
        }
    }, 3000);
}

// 批量点击所有空格子
async function batchTapAllEmpty() {
    const statusEl = document.getElementById('status');
    const deviceStatusEl = document.getElementById('device-status');
    const batchBtn = document.getElementById('batch-tap-empty-btn');

    if (!window.nonogramCore.currentGrid) {
        alert('点击空格前，请先求解数织！');
        return;
    }

    if (!proxyConnected) {
        alert('请先点击"测试连接"！');
        return;
    }

    // 收集所有空格子的坐标
    const emptyCells = [];
    for (let r = 0; r < window.nonogramCore.currentGrid.length; r++) {
        for (let c = 0; c < window.nonogramCore.currentGrid[r].length; c++) {
            if (window.nonogramCore.currentGrid[r][c] === window.nonogramCore.EMPTY) {
                const screenX = adbConfig.startX + c * adbConfig.cellWidth + Math.floor(adbConfig.cellWidth / 2);
                const screenY = adbConfig.startY + r * adbConfig.cellHeight + Math.floor(adbConfig.cellHeight / 2);
                emptyCells.push({ row: r, col: c, x: screenX, y: screenY });
            }
        }
    }

    if (emptyCells.length === 0) {
        alert('没有空格子！');
        return;
    }

    // 确认操作
    if (!confirm(`准备批量点击 ${emptyCells.length} 个空格子，确定继续吗？`)) {
        return;
    }

    // 禁用按钮
    batchBtn.disabled = true;
    batchBtn.textContent = '点击中...';

    let successCount = 0;
    let failCount = 0;

    // 依次点击每个格子
    for (let i = 0; i < emptyCells.length; i++) {
        const cell = emptyCells[i];
        statusEl.textContent = `正在点击空格子 (${cell.row + 1}, ${cell.col + 1})... (${i + 1}/${emptyCells.length})`;
        deviceStatusEl.textContent = `正在点击 (${cell.row + 1}, ${cell.col + 1})... (${i + 1}/${emptyCells.length})`;
        statusEl.className = 'device-connecting';
        deviceStatusEl.className = 'device-connecting';

        try {
            await executeTap(cell.x, cell.y);
            successCount++;
            // 添加小延迟，避免点击过快
            await new Promise(resolve => setTimeout(resolve, 100));
        } catch (error) {
            console.error(`点击 (${cell.row + 1}, ${cell.col + 1}) 失败:`, error);
            failCount++;
        }
    }

    // 恢复状态
    batchBtn.disabled = false;
    batchBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="3" y="3" width="10" height="10" rx="2" fill="none" stroke="currentColor" stroke-width="2"/></svg> 点击空格';

    if (failCount === 0) {
        statusEl.textContent = `✓ 批量点击空格完成！成功 ${successCount} 个`;
        deviceStatusEl.textContent = `✓ 批量点击完成！成功 ${successCount} 个`;
        statusEl.className = 'device-connected';
        deviceStatusEl.className = 'device-connected';
    } else {
        statusEl.textContent = `⚠ 批量点击空格完成！成功 ${successCount} 个，失败 ${failCount} 个`;
        deviceStatusEl.textContent = `⚠ 批量点击完成！成功 ${successCount} 个，失败 ${failCount} 个`;
        statusEl.className = 'device-disconnected';
        deviceStatusEl.className = 'device-disconnected';
    }

    // 3秒后恢复状态
    setTimeout(() => {
        if (proxyConnected) {
            statusEl.textContent = `✓ 设备已连接，可以点击格子进行操作`;
            deviceStatusEl.textContent = `✓ 代理已连接`;
            statusEl.className = 'device-connected';
            deviceStatusEl.className = 'device-connected';
        }
    }, 3000);
}

// 处理格子点击
async function handleCellClick(row, col, value) {
    // 计算屏幕坐标
    const screenX = adbConfig.startX + col * adbConfig.cellWidth + Math.floor(adbConfig.cellWidth / 2);
    const screenY = adbConfig.startY + row * adbConfig.cellHeight + Math.floor(adbConfig.cellHeight / 2);

    // 如果代理已连接，直接执行点击
    if (proxyConnected) {
        try {
            const statusEl = document.getElementById('status');
            const deviceStatusEl = document.getElementById('device-status');
            statusEl.textContent = `正在点击格子 (${row + 1}, ${col + 1})...`;
            deviceStatusEl.textContent = `正在点击 (${row + 1}, ${col + 1})...`;
            statusEl.className = 'device-connecting';
            deviceStatusEl.className = 'device-connecting';

            await executeTap(screenX, screenY);

            statusEl.textContent = `✓ 已点击格子 (${row + 1}, ${col + 1})`;
            deviceStatusEl.textContent = `✓ 已点击 (${row + 1}, ${col + 1})`;
            statusEl.className = 'device-connected';
            deviceStatusEl.className = 'device-connected';

            // 2秒后恢复状态
            setTimeout(() => {
                if (proxyConnected) {
                    statusEl.textContent = `✓ 设备已连接，可以点击格子进行操作`;
                    deviceStatusEl.textContent = `✓ 代理已连接`;
                    statusEl.className = 'device-connected';
                    deviceStatusEl.className = 'device-connected';
                }
            }, 2000);

        } catch (error) {
            console.error('点击失败:', error);
            const statusEl = document.getElementById('status');
            const deviceStatusEl = document.getElementById('device-status');
            statusEl.textContent = `✗ 点击失败: ${error.message}`;
            deviceStatusEl.textContent = `✗ 点击失败: ${error.message}`;
            statusEl.className = 'device-disconnected';
            deviceStatusEl.className = 'device-disconnected';
        }
    } else {
        // 代理未连接，显示命令供复制
        const cmd = `adb shell input tap ${screenX} ${screenY}`;
        showCommand(row, col, value, screenX, screenY, cmd);
    }
}

// 显示命令
function showCommand(row, col, value, x, y, cmd) {
    const display = document.getElementById('cmd-display');
    const info = document.getElementById('cmd-info');
    const text = document.getElementById('cmd-text');

    // 格式化格子状态
    let statusText = '';
    if (value === window.nonogramCore.FILLED) statusText = '填充';
    else if (value === window.nonogramCore.EMPTY) statusText = '空白';
    else statusText = '未知';

    info.innerHTML = `坐标: (${row + 1}, ${col + 1}) | 状态: ${statusText}<br>屏幕位置: X=${x}, Y=${y}`;
    text.textContent = cmd;

    display.classList.add('show');
}

// 隐藏命令
function hideCommand() {
    const display = document.getElementById('cmd-display');
    display.classList.remove('show');
}

// 复制命令
function copyCommand() {
    const cmd = document.getElementById('cmd-text').textContent;

    // 使用 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(cmd).then(() => {
            alert('命令已复制到剪贴板！');
        }).catch(err => {
            console.error('复制失败:', err);
            // 降级方案
            fallbackCopy(cmd);
        });
    } else {
        // 降级方案
        fallbackCopy(cmd);
    }
}

// 降级的复制方法
function fallbackCopy(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();

    try {
        document.execCommand('copy');
        alert('命令已复制到剪贴板！');
    } catch (err) {
        console.error('复制失败:', err);
        alert('复制失败，请手动复制');
    }

    document.body.removeChild(textarea);
}

// 打开 ADB 设置弹窗
function openAdbModal() {
    document.getElementById('adb-modal-overlay').classList.add('show');
}

// 关闭 ADB 设置弹窗
function closeAdbModal() {
    document.getElementById('adb-modal-overlay').classList.remove('show');
}

// 导出供其他模块使用
window.adbControls = {
    testProxyConnection,
    batchTapAllFilled,
    batchTapAllEmpty,
    handleCellClick,
    adbConfig,
    proxyConnected
};