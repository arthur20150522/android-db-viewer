document.addEventListener('DOMContentLoaded', function() {
    // State
    let state = {
        deviceId: null,
        package: null,
        dbToken: null,
        currentTable: null,
        limit: 50,
        offset: 0
    };

    // UI Elements
    const deviceSelect = document.getElementById('device-select');
    const rootStatus = document.getElementById('root-status');
    const refreshDevicesBtn = document.getElementById('refresh-devices');
    const packageSearch = document.getElementById('package-search');
    const packageList = document.getElementById('package-list');
    const dbCard = document.getElementById('db-card');
    const dbList = document.getElementById('db-list');
    const tableCard = document.getElementById('table-card');
    const tableList = document.getElementById('table-list');
    const dataControls = document.getElementById('data-controls');
    const currentTableName = document.getElementById('current-table-name');
    const dataTableContainer = document.getElementById('data-table-container');
    const pagination = document.getElementById('pagination');
    const prevPage = document.getElementById('prev-page');
    const nextPage = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');
    const runQueryBtn = document.getElementById('run-query');
    const queryResultContainer = document.getElementById('query-result-container');

    // Init CodeMirror
    const editor = CodeMirror.fromTextArea(document.getElementById('sql-editor'), {
        mode: 'text/x-sql',
        theme: 'monokai',
        lineNumbers: true
    });

    // --- API Calls ---

    async function fetchDevices() {
        deviceSelect.innerHTML = '<option>Loading...</option>';
        try {
            const res = await fetch('/api/devices');
            const devices = await res.json();
            deviceSelect.innerHTML = '<option value="">Select Device</option>';
            devices.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.id;
                opt.textContent = `${d.id} (${d.status})`;
                opt.dataset.root = d.root;
                deviceSelect.appendChild(opt);
            });
        } catch (e) {
            deviceSelect.innerHTML = '<option>Error loading devices</option>';
            console.error(e);
        }
    }

    async function fetchPackages(deviceId) {
        packageList.innerHTML = '<div class="p-2">Loading packages...</div>';
        try {
            const res = await fetch(`/api/packages/${deviceId}`);
            const packages = await res.json();
            renderPackages(packages);
        } catch (e) {
            packageList.innerHTML = '<div class="text-danger p-2">Error loading packages</div>';
        }
    }

    async function fetchDatabases(deviceId, pkg) {
        dbList.innerHTML = '<div class="p-2">Loading databases...</div>';
        dbCard.style.display = 'block';
        try {
            const res = await fetch(`/api/databases/${deviceId}/${pkg}`);
            const dbs = await res.json();
            renderDatabases(dbs);
        } catch (e) {
            dbList.innerHTML = '<div class="text-danger p-2">Error loading databases</div>';
        }
    }

    async function pullDatabase(deviceId, pkg, dbName) {
        // Show loading state
        tableList.innerHTML = '<div class="p-2">Pulling database...</div>';
        tableCard.style.display = 'block';
        
        try {
            const res = await fetch('/api/pull', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    device_id: deviceId,
                    package_name: pkg,
                    db_name: dbName
                })
            });
            const data = await res.json();
            if (data.success) {
                state.dbToken = data.token;
                fetchTables(data.token);
            } else {
                tableList.innerHTML = `<div class="text-danger p-2">${data.error}</div>`;
            }
        } catch (e) {
            tableList.innerHTML = '<div class="text-danger p-2">Error pulling database</div>';
        }
    }

    async function fetchTables(token) {
        try {
            const res = await fetch(`/api/tables/${token}`);
            const tables = await res.json();
            renderTables(tables);
        } catch (e) {
            tableList.innerHTML = '<div class="text-danger p-2">Error loading tables</div>';
        }
    }

    async function fetchTableData(token, table, resetPage=true) {
        if (resetPage) state.offset = 0;
        
        dataTableContainer.innerHTML = '<div class="p-3">Loading data...</div>';
        dataControls.style.display = 'flex'; // Important: using flex here to match d-flex
        currentTableName.textContent = table;
        
        try {
            const res = await fetch(`/api/table/${token}/${table}?limit=${state.limit}&offset=${state.offset}`);
            const data = await res.json();
            renderTableData(data.columns, data.rows, dataTableContainer);
            updatePagination(data.total);
        } catch (e) {
            dataTableContainer.innerHTML = '<div class="text-danger p-3">Error loading data</div>';
        }
    }

    async function executeQuery() {
        if (!state.dbToken) {
            alert('Please select a database first.');
            return;
        }
        
        const query = editor.getValue();
        queryResultContainer.innerHTML = '<div class="p-3">Executing...</div>';
        
        try {
            const res = await fetch(`/api/query/${state.dbToken}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query})
            });
            const data = await res.json();
            
            if (data.error) {
                queryResultContainer.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            } else if (data.message) {
                queryResultContainer.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
            } else {
                renderTableData(data.columns, data.rows, queryResultContainer);
            }
        } catch (e) {
            queryResultContainer.innerHTML = '<div class="text-danger p-3">Error executing query</div>';
        }
    }

    // --- Render Helpers ---

    let allPackages = [];
    function renderPackages(packages) {
        allPackages = packages;
        filterPackages();
    }

    function filterPackages() {
        const term = packageSearch.value.toLowerCase();
        const filtered = allPackages.filter(p => p.toLowerCase().includes(term));
        
        packageList.innerHTML = '';
        filtered.forEach(p => {
            const item = document.createElement('a');
            item.className = 'list-group-item list-group-item-action';
            item.textContent = p;
            item.onclick = () => {
                // Highlight
                document.querySelectorAll('#package-list .active').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                
                state.package = p;
                fetchDatabases(state.deviceId, p);
            };
            packageList.appendChild(item);
        });
    }

    function renderDatabases(dbs) {
        dbList.innerHTML = '';
        if (dbs.length === 0) {
            dbList.innerHTML = '<div class="p-2 text-muted">No databases found or permission denied.</div>';
            return;
        }
        dbs.forEach(db => {
            const item = document.createElement('a');
            item.className = 'list-group-item list-group-item-action';
            item.textContent = db;
            item.onclick = () => {
                document.querySelectorAll('#db-list .active').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                pullDatabase(state.deviceId, state.package, db);
            };
            dbList.appendChild(item);
        });
    }

    function renderTables(tables) {
        tableList.innerHTML = '';
        tables.forEach(t => {
            const item = document.createElement('a');
            item.className = 'list-group-item list-group-item-action';
            item.textContent = t;
            item.onclick = () => {
                document.querySelectorAll('#table-list .active').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                state.currentTable = t;
                fetchTableData(state.dbToken, t);
            };
            tableList.appendChild(item);
        });
    }

    function renderTableData(columns, rows, container) {
        if (!rows || rows.length === 0) {
            container.innerHTML = '<div class="p-3 text-muted">No data found.</div>';
            return;
        }

        let html = '<table class="table table-bordered table-hover table-sm"><thead><tr>';
        columns.forEach(col => {
            html += `<th>${col}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        rows.forEach(row => {
            html += '<tr>';
            columns.forEach(col => {
                html += `<td>${row[col] !== null ? row[col] : '<span class="text-muted">NULL</span>'}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    function updatePagination(total) {
        if (total > state.limit) {
            pagination.style.display = 'block';
            const currentPage = Math.floor(state.offset / state.limit) + 1;
            pageInfo.textContent = `Page ${currentPage} (Total: ${total})`;
            
            prevPage.parentElement.classList.toggle('disabled', state.offset === 0);
            nextPage.parentElement.classList.toggle('disabled', state.offset + state.limit >= total);
        } else {
            pagination.style.display = 'none';
        }
    }

    // --- Event Listeners ---

    refreshDevicesBtn.onclick = fetchDevices;

    deviceSelect.onchange = () => {
        const selected = deviceSelect.options[deviceSelect.selectedIndex];
        state.deviceId = selected.value;
        // Fix: JSON boolean 'true' becomes string 'true' in dataset, not 'True'
        const isRoot = selected.dataset.root === 'true'; 
        
        if (state.deviceId) {
            rootStatus.textContent = isRoot ? '✅ Rooted' : '❌ Not Rooted';
            rootStatus.className = isRoot ? 'mt-1 small text-success' : 'mt-1 small text-danger';
            if (isRoot) {
                fetchPackages(state.deviceId);
            } else {
                packageList.innerHTML = '<div class="text-warning p-2">Device must be rooted to access databases.</div>';
            }
        } else {
            rootStatus.textContent = '';
            packageList.innerHTML = '';
        }
        
        // Reset downstream
        dbCard.style.display = 'none';
        tableCard.style.display = 'none';
        dataTableContainer.innerHTML = '';
        state.package = null;
        state.dbToken = null;
    };

    packageSearch.onkeyup = filterPackages;

    prevPage.onclick = (e) => {
        e.preventDefault();
        if (state.offset > 0) {
            state.offset -= state.limit;
            fetchTableData(state.dbToken, state.currentTable, false);
        }
    };

    nextPage.onclick = (e) => {
        e.preventDefault();
        state.offset += state.limit;
        fetchTableData(state.dbToken, state.currentTable, false);
    };

    runQueryBtn.onclick = executeQuery;

    // Initial load
    fetchDevices();
});
