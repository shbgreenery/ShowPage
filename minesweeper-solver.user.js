// ==UserScript==
// @name         Minesweeper Solver (Advanced - Set Difference)
// @namespace    http://tampermonkey.net/
// @version      0.3
// @description  Solves minesweeper using Single Cell analysis and Set Difference (1-2-1 patterns)
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
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const rect = canvas.getBoundingClientRect();
        const cellSize = 25;

        // 本次计算新发现的雷和安全格
        const newMines = new Set();
        const newSafes = new Set();

        let changed = true;

        // 获取唯一的Key
        const getKey = (r, c) => `${r},${c}`;
        const parseKey = (k) => k.split(',').map(Number);

        // 获取某个格子的有效未知邻居 (排除已知的安全格)
        const getAnalysisData = (r, c) => {
            let unknown = [];
            let knownMines = 0; // 物理旗子 + 虚拟雷

            for (let ni = -1; ni <= 1; ni++) {
                for (let nj = -1; nj <= 1; nj++) {
                    if (ni === 0 && nj === 0) continue;
                    const nr = r + ni, nc = c + nj;
                    if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
                        const k = getKey(nr, nc);
                        const isPhysFlag = board[nr][nc][0] === 2;
                        const isPhysUnopened = board[nr][nc][0] === 0;
                        const isVirtMine = newMines.has(k);
                        const isVirtSafe = newSafes.has(k);

                        if (isPhysFlag || isVirtMine) {
                            knownMines++;
                        } else if (isPhysUnopened && !isVirtSafe) {
                            unknown.push(k);
                        }
                    }
                }
            }
            return {
                r, c,
                val: board[r][c][2],
                knownMines,
                remainingNeeded: board[r][c][2] - knownMines,
                unknownNeighbors: unknown
            };
        };

        // 主循环：只要有新发现就继续推导
        while (changed) {
            changed = false;
            let currentChanges = 0;

            // 1. 收集所有边界上的数字格子的信息
            // 这一点很重要，把所有需要分析的格子数据化
            let boundaryCells = [];

            for (let i = 0; i < rows; i++) {
                for (let j = 0; j < cols; j++) {
                    // 只关心已打开且未满足的数字
                    if (board[i][j][0] === 1 && board[i][j][2] > 0) {
                        const data = getAnalysisData(i, j);
                        // 如果已经满足了，跳过
                        if (data.unknownNeighbors.length === 0 && data.remainingNeeded === 0) continue;

                        // 基础逻辑检查 (Single Square)
                        if (data.remainingNeeded === 0 && data.unknownNeighbors.length > 0) {
                            // 剩余雷数0 -> 全是安全
                            data.unknownNeighbors.forEach(k => {
                                if (!newSafes.has(k)) { newSafes.add(k); changed = true; currentChanges++; }
                            });
                        } else if (data.remainingNeeded === data.unknownNeighbors.length) {
                            // 剩余雷数=未知格数 -> 全是雷
                            data.unknownNeighbors.forEach(k => {
                                if (!newMines.has(k)) { newMines.add(k); changed = true; currentChanges++; }
                            });
                        } else {
                            // 没能直接解开，加入待分析列表
                            boundaryCells.push(data);
                        }
                    }
                }
            }

            // 如果基础逻辑已经发现了东西，先不跑高级逻辑，提高效率并防止冲突
            if (changed) continue;

            // 2. 高级逻辑：集合差分 (Set Difference)
            // 比较列表中的任意两个格子 A 和 B
            // 如果 A 的未知邻居是 B 的未知邻居的子集，则可以做减法

            // 为了性能，只比较距离较近的格子 (曼哈顿距离 <= 2 或者 3)
            // 这里简单点，全量比较（因为 boundaryCells 通常不会特别多），或者只比较重叠的

            for (let i = 0; i < boundaryCells.length; i++) {
                for (let j = 0; j < boundaryCells.length; j++) {
                    if (i === j) continue;

                    const A = boundaryCells[i];
                    const B = boundaryCells[j];

                    // 优化：如果两者距离太远，不可能重叠，跳过
                    if (Math.abs(A.r - B.r) > 2 || Math.abs(A.c - B.c) > 2) continue;

                    // 检查 A 是否是 B 的子集
                    // 即：A 的所有未知邻居都在 B 的未知邻居里
                    // 注意：这里需要精确匹配字符串key

                    // 快速检查长度，A 必须比 B 短或相等
                    if (A.unknownNeighbors.length > B.unknownNeighbors.length) continue;

                    const setB = new Set(B.unknownNeighbors);
                    const isSubset = A.unknownNeighbors.every(k => setB.has(k));

                    if (isSubset) {
                        // 核心数学逻辑
                        const diffMines = B.remainingNeeded - A.remainingNeeded;
                        const diffNeighbors = B.unknownNeighbors.filter(k => !A.unknownNeighbors.includes(k));

                        // 差集区域里的情况
                        if (diffNeighbors.length > 0) {
                            // 情况 1: B 比 A 多需要的雷数 == 0
                            // 这意味着 B 所有的雷都在 A 的区域里找到了
                            // 所以 B 独有的区域全是安全的
                            if (diffMines === 0) {
                                diffNeighbors.forEach(k => {
                                    if (!newSafes.has(k)) {
                                        newSafes.add(k);
                                        changed = true;
                                    }
                                });
                            }

                            // 情况 2: B 比 A 多需要的雷数 == B 独有区域的格子数
                            // 这意味着 B 独有的区域必须全是雷才能满足差额
                            else if (diffMines === diffNeighbors.length) {
                                diffNeighbors.forEach(k => {
                                    if (!newMines.has(k)) {
                                        newMines.add(k);
                                        changed = true;
                                    }
                                });
                            }
                        }
                    }
                }
                if (changed) break; // 如果发现变化，跳出内层循环，重新计算全局状态
            }
        }

        // --- 执行绘制与点击 ---
        newMines.forEach(k => {
            const [r, c] = parseKey(k);
            ctx.fillStyle = 'red';
            ctx.fillRect(c * cellSize + 10, r * cellSize + 10, 5, 5);
        });

        newSafes.forEach(k => {
            const [r, c] = parseKey(k);
            if (document.getElementById('autoClick').checked) {
                const x = c * cellSize + cellSize / 2;
                const y = r * cellSize + cellSize / 2;
                const events = ['mousedown', 'mouseup', 'click'];
                events.forEach(etype => {
                    canvas.dispatchEvent(new MouseEvent(etype, {
                        clientX: rect.left + x,
                        clientY: rect.top + y,
                        button: 0,
                        bubbles: true
                    }));
                });
            } else {
                ctx.fillStyle = '#00FF00'; // 亮绿色
                ctx.fillRect(c * cellSize + 8, r * cellSize + 8, 9, 9);
            }
        });
    }

    // --- UI Setup ---
    const controls = document.createElement('div');
    Object.assign(controls.style, {
        position: 'absolute', top: '10px', left: '10px', zIndex: '9999',
        backgroundColor: 'rgba(0,0,0,0.7)', padding: '10px', borderRadius: '8px', color: 'white',
        fontFamily: 'Arial, sans-serif'
    });

    const btn = document.createElement('button');
    btn.textContent = '⚡ Solve Step';
    btn.onclick = solve;
    Object.assign(btn.style, { marginRight: '10px', padding: '5px 10px', cursor: 'pointer' });

    const chkClick = document.createElement('input');
    chkClick.type = 'checkbox';
    chkClick.id = 'autoClick';
    const lblClick = document.createElement('label');
    lblClick.textContent = ' Auto Click';
    lblClick.htmlFor = 'autoClick';
    lblClick.style.marginRight = '10px';

    const chkLoop = document.createElement('input');
    chkLoop.type = 'checkbox';
    chkLoop.id = 'autoLoop';
    const lblLoop = document.createElement('label');
    lblLoop.textContent = ' Continuous';
    lblLoop.htmlFor = 'autoLoop';

    controls.append(btn, chkClick, lblClick, chkLoop, lblLoop);
    document.body.appendChild(controls);

    let timer = null;
    chkLoop.onchange = (e) => {
        if (e.target.checked) {
            timer = setInterval(solve, 500);
            solve();
        } else {
            clearInterval(timer);
        }
    };
})();