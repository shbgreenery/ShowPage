// 数织求解器核心逻辑和算法

// 状态常量
const UNKNOWN = -1; // 使用-1表示未知，与Python版本一致
const FILLED = 1;
const EMPTY = 0;

// 当前网格数据（用于批量点击）
let currentGrid = null;

// 主求解函数
function solve() {
    const statusEl = document.getElementById('status');
    const resultArea = document.getElementById('result-area');
    resultArea.classList.remove('show');
    resultArea.innerHTML = '';
    statusEl.textContent = "正在求解...";

    // 1. 解析输入
    const rowsInput = parseConstraints(document.getElementById('row-constraints').value);
    const colsInput = parseConstraints(document.getElementById('col-constraints').value);

    if (rowsInput.length === 0 || colsInput.length === 0) {
        statusEl.textContent = "错误：请输入有效的行和列约束。";
        return;
    }

    // 限制最多20行
    if (rowsInput.length > 20 || colsInput.length > 20) {
        statusEl.textContent = "错误：行数和列数不能超过20。";
        return;
    }

    if (rowsInput.length !== colsInput.length) {
        statusEl.textContent = "错误：行数和列数必须相等。";
        return;
    }

    const n = rowsInput.length;

    // 2. 初始化网格 (-1=未知, 1=填, 0=空)
    let grid = Array(n).fill().map(() => Array(n).fill(UNKNOWN));

    // 3. 调用移植的Python算法
    try {
        const solution = solveNonogram(rowsInput, colsInput);

        // 4. 渲染结果
        renderGrid(solution, rowsInput, colsInput);

        statusEl.textContent = "求解成功！";
        resultArea.classList.add('show');
    } catch (e) {
        statusEl.textContent = e.message;
    }
}

// 非ogram求解算法（移植自Python版本）
function solveNonogram(rows, cols) {
    const n = rows.length;
    if (n !== cols.length) {
        throw new Error("行数和列数不一致");
    }

    const ans = Array(n).fill().map(() => Array(n).fill(-1));

    // 将rows和cols转换为元组
    const rowsTuple = rows.map(row => JSON.stringify(row));
    const colsTuple = cols.map(col => JSON.stringify(col));

    // 将整数转换为二进制字符串
    function int2str(i) {
        let si = i.toString(2);
        return '0'.repeat(n - si.length) + si;
    }

    // 将二进制字符串转换为数组
    function str2arr(s) {
        const tmp = [];
        for (let i = 0; i < s.length; i++) {
            const c = s[i];
            if (c === '1') {
                if (i === 0 || s[i - 1] === '0') {
                    tmp.push(1);
                } else {
                    tmp[tmp.length - 1] += 1;
                }
            }
        }
        return tmp;
    }

    // 设置函数
    function f1(i, j) {
        ans[i][j] = 1;
        for (const p of [...prow[i]]) { // 创建副本以避免迭代时修改
            if (p[j] === '0') {
                prow[i].delete(p);
            }
        }
        for (const p of [...pcol[j]]) { // 创建副本以避免迭代时修改
            if (p[i] === '0') {
                pcol[j].delete(p);
            }
        }
    }

    function f0(i, j) {
        ans[i][j] = 0;
        for (const p of [...prow[i]]) { // 创建副本以避免迭代时修改
            if (p[j] === '1') {
                prow[i].delete(p);
            }
        }
        for (const p of [...pcol[j]]) { // 创建副本以避免迭代时修改
            if (p[i] === '1') {
                pcol[j].delete(p);
            }
        }
    }

    // 创建所有可能状态的映射
    const cs = new Map();
    for (let state = 0; state < (1 << n); state++) {
        const strState = int2str(state);
        const arrState = str2arr(strState);

        // 添加对应的状态
        const arrKey = JSON.stringify(arrState);
        if (!cs.has(arrKey)) {
            cs.set(arrKey, []);
        }
        cs.get(arrKey).push(strState);

        // 为未确定的线索添加所有状态
        const unmarkedKey = JSON.stringify([-1]);
        if (!cs.has(unmarkedKey)) {
            cs.set(unmarkedKey, []);
        }
        cs.get(unmarkedKey).push(strState);
    }

    // 初始化行和列的可能状态集合
    const prow = Array(n).fill().map(() => new Set());
    const pcol = Array(n).fill().map(() => new Set());

    for (let i = 0; i < n; i++) {
        const rowKey = rowsTuple[i];
        if (cs.has(rowKey)) {
            for (const p of cs.get(rowKey)) {
                prow[i].add(p);
            }
        }

        const colKey = colsTuple[i];
        if (cs.has(colKey)) {
            for (const p of cs.get(colKey)) {
                pcol[i].add(p);
            }
        }
    }

    // 迭代直到没有变化
    while (true) {
        let change = false;

        for (let i = 0; i < n; i++) {
            // 处理行
            const ps = prow[i];
            const cnt = Array(n).fill(0);

            for (const p of ps) {
                for (let j = 0; j < n; j++) {
                    if (p[j] === '1') {
                        cnt[j]++;
                    }
                }
            }

            for (let j = 0; j < n; j++) {
                if (ans[i][j] == EMPTY && cnt[j] == ps.size) {
                    throw new Error(`冲突在位置 (${i}, ${j})`);
                }
                if (ans[i][j] === -1 && cnt[j] === ps.size) {
                    f1(i, j);
                    change = true;
                }
                if (ans[i][j] == FILLED && cnt[j] == 0) {
                    throw new Error(`冲突在位置 (${i}, ${j})`);
                }
                if (ans[i][j] === -1 && cnt[j] === 0) {
                    f0(i, j);
                    change = true;
                }
            }
        }

        for (let i = 0; i < n; i++) {
            // 处理列
            const ps = pcol[i];
            const cnt = Array(n).fill(0);

            for (const p of ps) {
                for (let j = 0; j < n; j++) {
                    if (p[j] === '1') {
                        cnt[j]++;
                    }
                }
            }

            for (let j = 0; j < n; j++) {
                if (ans[j][i] == EMPTY && cnt[j] == ps.size) {
                    throw new Error(`冲突在位置 (${j}, ${i})`);
                }
                if (ans[j][i] == FILLED && cnt[j] == 0) {
                    throw new Error(`冲突在位置 (${j}, ${i})`);
                }
                if (ans[j][i] === -1 && cnt[j] === ps.size) {
                    f1(j, i);
                    change = true;
                }
                if (ans[j][i] === -1 && cnt[j] === 0) {
                    f0(j, i);
                    change = true;
                }
            }
        }

        if (!change) {
            break;
        }
    }

    return ans;
}

// 解析函数，与Python版本兼容
function parseConstraints(text) {
    if (!text || !text.trim()) return [];

    // 按行分割，去除首尾空白
    const lines = text.trim().split('\n');

    return lines.map(line => {
        // 提取所有数字，使用-1表示未确定的约束
        const tokens = line.trim().split(/\s+/);
        const result = [];

        for (const token of tokens) {
            if (token === '?') {
                result.push(-1); // 使用-1表示未确定的约束
            } else if (/\d+/.test(token)) {
                result.push(Number(token));
            }
        }

        return result;
    });
}

function renderGrid(grid, rowHints, colHints) {
    const container = document.getElementById('result-area');
    container.innerHTML = '';

    // 保存当前网格数据用于批量点击
    currentGrid = grid;

    const rows = grid.length;
    const cols = grid[0].length;

    const gridEl = document.createElement('div');
    gridEl.className = 'nono-grid';

    gridEl.style.gridTemplateColumns = `auto repeat(${cols}, var(--cell-size))`;
    gridEl.style.gridTemplateRows = `auto repeat(${rows}, var(--cell-size))`;

    // 1. 左上角空白
    const corner = document.createElement('div');
    corner.className = 'corner';
    gridEl.appendChild(corner);

    // 2. 顶部列提示
    for (let c = 0; c < cols; c++) {
        const hintEl = document.createElement('div');
        hintEl.className = 'hint col-hint';
        // 处理包含-1的提示显示
        const hintContent = colHints[c].map(val => val === -1 ? '?' : val).join('<br>');
        hintEl.innerHTML = hintContent;
        gridEl.appendChild(hintEl);
    }

    // 3. 生成每一行
    for (let r = 0; r < rows; r++) {
        // 行提示
        const rowHintEl = document.createElement('div');
        rowHintEl.className = 'hint row-hint';
        // 处理包含-1的提示显示
        const hintContent = rowHints[r].map(val => val === -1 ? '?' : val).join(' ');
        rowHintEl.textContent = hintContent;
        gridEl.appendChild(rowHintEl);

        // 单元格
        for (let c = 0; c < cols; c++) {
            const cell = document.createElement('div');
            cell.className = 'cell clickable';
            const val = grid[r][c];

            if (val === FILLED) cell.classList.add('filled');
            else if (val === EMPTY) cell.classList.add('empty');
            else if (val === UNKNOWN) cell.classList.add('unknown'); // 未知格子显示问号

            // 粗边框
            if ((c + 1) % 5 === 0 && c !== cols - 1) cell.classList.add('border-right');
            if ((r + 1) % 5 === 0 && r !== rows - 1) cell.classList.add('border-bottom');

            // 添加点击事件
            cell.onclick = function () {
                handleCellClick(r, c, val);
            };

            gridEl.appendChild(cell);
        }
    }

    container.appendChild(gridEl);
}

function loadSample() {
    // 示例：一个 3x3 的简单图案
    const sampleRows =
        `-1
1 1
3`;
    const sampleCols =
        `-1
1 1
3`;

    document.getElementById('row-constraints').value = sampleRows;
    document.getElementById('col-constraints').value = sampleCols;

    solve();
}

function clearConstraints() {
    document.getElementById('row-constraints').value = '';
    document.getElementById('col-constraints').value = '';
    document.getElementById('result-area').classList.remove('show');
    document.getElementById('result-area').innerHTML = '<div style="display: flex; justify-content: center; align-items: center; height: 100%; color: #999; font-style: italic;">结果将显示在这里</div>';
    document.getElementById('status').textContent = '';
}

// 导出供其他模块使用
window.nonogramCore = {
    solve,
    loadSample,
    clearConstraints,
    currentGrid,
    UNKNOWN,
    FILLED,
    EMPTY
};