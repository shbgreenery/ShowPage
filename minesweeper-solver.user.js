// ==UserScript==
// @name         Minesweeper Solver
// @namespace    http://tampermonkey.net/
// @version      0.1
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

        // --- REVISED AND OPTIMIZED LOGIC ---
        // 1. 在所有循环之外获取一次canvas和它的属性，以提高效率
        const canvas = document.getElementById('paf');
        if (!canvas) {
            console.error("Minesweeper canvas not found!");
            return; // 如果找不到canvas，则退出函数
        }
        const ctx = canvas.getContext('2d');
        const rect = canvas.getBoundingClientRect(); // 在函数开头定义rect
        const cellSize = 25; // 单元格的大约尺寸

        // 遍历棋盘寻找线索
        for (let i = 0; i < rows; i++) {
            for (let j = 0; j < cols; j++) {
                // 如果这个单元格是已打开的数字
                if (board[i][j][0] === 1 && board[i][j][2] > 0) {
                    let unopenedNeighbors = [];
                    let flaggedNeighbors = 0;

                    // 检查周围的8个邻居
                    for (let ni = -1; ni <= 1; ni++) {
                        for (let nj = -1; nj <= 1; nj++) {
                            if (ni === 0 && nj === 0) continue;

                            const ni_ = i + ni;
                            const nj_ = j + nj;

                            if (ni_ >= 0 && ni_ < rows && nj_ >= 0 && nj_ < cols) {
                                if (board[ni_][nj_][0] === 0) { // 未打开
                                    unopenedNeighbors.push({ r: ni_, c: nj_ });
                                } else if (board[ni_][nj_][0] === 2) { // 已插旗
                                    flaggedNeighbors++;
                                }
                            }
                        }
                    }

                    // 规则1：如果已标记的旗子数等于数字，则剩余未打开的邻居是安全的
                    if (flaggedNeighbors === board[i][j][2]) {
                        unopenedNeighbors.forEach(cell => {
                            if (autoClickCheckbox.checked) {
                                // 计算单元格在canvas上的精确坐标
                                const x = cell.c * cellSize + cellSize / 2;
                                const y = cell.r * cellSize + cellSize / 2;

                                // 创建一个模拟鼠标事件，现在可以安全地使用在函数开头定义的 'rect'
                                const clickEvent = new MouseEvent('mousedown', {
                                    clientX: rect.left + x,
                                    clientY: rect.top + y,
                                    button: 0 // 0 代表鼠标左键
                                });

                                // 在canvas上触发这个点击事件
                                canvas.dispatchEvent(clickEvent);
                            } else {
                                // 使用在函数开头定义的 'ctx' 来绘制提示
                                ctx.fillStyle = 'green';
                                ctx.fillRect(cell.c * cellSize + 10, cell.r * cellSize + 10, 5, 5);
                            }
                        });
                    }

                    // 规则2：如果未打开的邻居数 + 已标记的旗子数等于数字，则所有未打开的邻居都是地雷
                    if (unopenedNeighbors.length + flaggedNeighbors === board[i][j][2]) {
                        unopenedNeighbors.forEach(cell => {
                            // 使用在函数开头定义的 'ctx' 来绘制提示
                            ctx.fillStyle = 'red';
                            ctx.fillRect(cell.c * cellSize + 10, cell.r * cellSize + 10, 5, 5);
                        });
                    }
                }
            }
        }
    }

    const controls = document.createElement('div');
    controls.style.position = 'absolute';
    controls.style.top = '10px';
    controls.style.left = '10px';
    controls.style.zIndex = '1000';

    const solveButton = document.createElement('button');
    solveButton.innerHTML = 'Solve';
    solveButton.onclick = solve;

    const autoClickCheckbox = document.createElement('input');
    autoClickCheckbox.type = 'checkbox';
    autoClickCheckbox.id = 'autoClick';
    const autoClickLabel = document.createElement('label');
    autoClickLabel.innerHTML = 'Auto Click';
    autoClickLabel.htmlFor = 'autoClick';

    const autoRefreshCheckbox = document.createElement('input');
    autoRefreshCheckbox.type = 'checkbox';
    autoRefreshCheckbox.id = 'autoRefresh';
    const autoRefreshLabel = document.createElement('label');
    autoRefreshLabel.innerHTML = 'Auto Refresh';
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
            solveInterval = setInterval(solve, 1000);
        } else {
            clearInterval(solveInterval);
        }
    });
})();
