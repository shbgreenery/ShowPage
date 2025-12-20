// ==UserScript==
// @name         Minesweeper Solver (Optimized)
// @namespace    http://tampermonkey.net/
// @version      0.2
// @description  A script to help solve the minesweeper game on minesweeper.cn
// @author       You
// @match        https://www.minesweeper.cn/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    function solve() {
        const rows = window.v;
        const cols = window.m;
        const board = window.d;

        const canvas = document.getElementById('paf');
        if (!canvas) {
            console.error("Minesweeper canvas not found!");
            return;
        }
        const ctx = canvas.getContext('2d');
        const rect = canvas.getBoundingClientRect();
        const cellSize = 25;

        // --- 核心逻辑优化 ---
        // 使用 Set 存储本次计算中新发现的雷和安全格的坐标 "row,col"
        // 这样可以在同一次 solve 调用中实现连锁推导
        const newMines = new Set();
        const newSafes = new Set();
        let changed = true;

        // 循环推导，直到没有新的结果产生（连锁反应）
        // 比如：发现一个雷后，利用这个雷的信息去推导旁边的数字，可能立即发现安全格
        while (changed) {
            changed = false;

            for (let i = 0; i < rows; i++) {
                for (let j = 0; j < cols; j++) {
                    // 只处理已打开且有数字的格子
                    if (board[i][j][0] === 1 && board[i][j][2] > 0) {

                        let unknownNeighbors = [];
                        let knownMineCount = 0; // 包括已插旗 和 本次推断出的雷

                        // 检查周围的8个邻居
                        for (let ni = -1; ni <= 1; ni++) {
                            for (let nj = -1; nj <= 1; nj++) {
                                if (ni === 0 && nj === 0) continue;

                                const r = i + ni;
                                const c = j + nj;

                                if (r >= 0 && r < rows && c >= 0 && c < cols) {
                                    const key = `${r},${c}`;

                                    // 状态判断
                                    const isPhysicalFlag = (board[r][c][0] === 2);
                                    const isPhysicalUnopened = (board[r][c][0] === 0);
                                    const isVirtualMine = newMines.has(key);
                                    const isVirtualSafe = newSafes.has(key);

                                    // 统计已知雷 (物理旗子 OR 推断出的雷)
                                    if (isPhysicalFlag || isVirtualMine) {
                                        knownMineCount++;
                                    }

                                    // 统计未知格子 (物理未打开 AND 不是旗子 AND 没被推断为雷 AND 没被推断为安全)
                                    // 重点：这里排除了 isVirtualSafe，实现了“计算雷的时候考虑已计算出的非雷”
                                    else if (isPhysicalUnopened && !isVirtualSafe) {
                                        unknownNeighbors.push({ r: r, c: c, key: key });
                                    }
                                }
                            }
                        }

                        const cellValue = board[i][j][2];

                        // 规则1：如果 (已知雷 + 推断雷) == 数字，则剩余所有未知邻居都是安全的
                        if (knownMineCount === cellValue && unknownNeighbors.length > 0) {
                            unknownNeighbors.forEach(cell => {
                                if (!newSafes.has(cell.key)) {
                                    newSafes.add(cell.key);
                                    changed = true; // 标记发生变化，需要再次循环
                                }
                            });
                        }

                        // 规则2：如果 (已知雷 + 推断雷) + 剩余未知邻居数 == 数字，则剩余所有未知邻居都是雷
                        if (knownMineCount + unknownNeighbors.length === cellValue && unknownNeighbors.length > 0) {
                            unknownNeighbors.forEach(cell => {
                                if (!newMines.has(cell.key)) {
                                    newMines.add(cell.key);
                                    changed = true; // 标记发生变化，需要再次循环
                                }
                            });
                        }
                    }
                }
            }
        }

        // --- 执行操作 ---
        // 所有的推导结束后，统一进行绘制或点击，避免重复操作

        // 1. 标记雷 (绘制红色)
        newMines.forEach(key => {
            const [r, c] = key.split(',').map(Number);
            // 绘制红色标记
            ctx.fillStyle = 'red';
            ctx.fillRect(c * cellSize + 10, r * cellSize + 10, 5, 5);

            // 可选：如果想自动插旗，可以在这里添加右键点击逻辑
            // 但为了安全起见，通常只自动点击安全格
        });

        // 2. 点击安全格 (自动点击 或 绘制绿色)
        newSafes.forEach(key => {
            const [r, c] = key.split(',').map(Number);

            if (autoClickCheckbox.checked) {
                const x = c * cellSize + cellSize / 2;
                const y = r * cellSize + cellSize / 2;

                const clickEvent = new MouseEvent('mousedown', {
                    clientX: rect.left + x,
                    clientY: rect.top + y,
                    button: 0 // 左键点击
                });
                const mouseUpEvent = new MouseEvent('mouseup', {
                    clientX: rect.left + x,
                    clientY: rect.top + y,
                    button: 0
                });
                // 有些游戏引擎需要完整的 down/up 流程
                canvas.dispatchEvent(clickEvent);
                canvas.dispatchEvent(mouseUpEvent);
            } else {
                ctx.fillStyle = 'green';
                ctx.fillRect(c * cellSize + 10, r * cellSize + 10, 5, 5);
            }
        });
    }

    // --- UI 构建 (保持不变) ---
    const controls = document.createElement('div');
    controls.style.position = 'absolute';
    controls.style.top = '10px';
    controls.style.left = '10px';
    controls.style.zIndex = '1000';
    controls.style.backgroundColor = 'rgba(255,255,255,0.8)'; // 加个背景色防止看不清
    controls.style.padding = '5px';
    controls.style.borderRadius = '5px';

    const solveButton = document.createElement('button');
    solveButton.innerHTML = 'Solve Once';
    solveButton.onclick = solve;
    solveButton.style.marginRight = '10px';

    const autoClickCheckbox = document.createElement('input');
    autoClickCheckbox.type = 'checkbox';
    autoClickCheckbox.id = 'autoClick';
    const autoClickLabel = document.createElement('label');
    autoClickLabel.innerHTML = 'Auto Click Safe';
    autoClickLabel.htmlFor = 'autoClick';
    autoClickLabel.style.marginRight = '10px';

    const autoRefreshCheckbox = document.createElement('input');
    autoRefreshCheckbox.type = 'checkbox';
    autoRefreshCheckbox.id = 'autoRefresh';
    const autoRefreshLabel = document.createElement('label');
    autoRefreshLabel.innerHTML = 'Auto Refresh (Loop)';
    autoRefreshLabel.htmlFor = 'autoRefresh';

    controls.appendChild(solveButton);
    controls.appendChild(autoClickCheckbox);
    controls.appendChild(autoClickLabel);
    controls.appendChild(autoRefreshCheckbox);
    controls.appendChild(autoRefreshLabel);
    document.body.appendChild(controls);

    let solveInterval = null;
    autoRefreshCheckbox.addEventListener('change', (event) => {
        if (event.currentTarget.checked) {
            // 稍微加快一点频率，因为现在的算法单次效率更高
            solveInterval = setInterval(solve, 800);
            solve(); // 立即执行一次
        } else {
            clearInterval(solveInterval);
        }
    });
})();