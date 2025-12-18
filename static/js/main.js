document.addEventListener('DOMContentLoaded', function() {
    // State
    let state = {
        deviceId: null,
        package: null,
        dbToken: null,
        openTabs: {}, // table_name -> { offset, limit, intervalId }
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
    
    // Tabs
    const mainTabs = document.getElementById('main-tabs');
    const tabContent = document.getElementById('myTabContent');
    const sqlTabBtn = document.getElementById('sql-tab');
    
    const runQueryBtn = document.getElementById('run-query');
    const queryResultContainer = document.getElementById('query-result-container');
    const queryHistoryContainer = document.getElementById('query-history');
    let historyCount = 0;

    // Init CodeMirror
    const editor = CodeMirror.fromTextArea(document.getElementById('sql-editor'), {
        mode: 'text/x-sql',
        theme: 'monokai',
        lineNumbers: true,
        gutters: ["CodeMirror-linenumbers"],
        extraKeys: {"Ctrl-Space": "autocomplete"},
        hintOptions: {
            tables: {} // Will be populated dynamically
        }
    });

    // Update hints when typing
    editor.on("keyup", function (cm, event) {
        if (!cm.state.completionActive && /*Enables keyboard navigation in autocomplete list*/
            event.keyCode > 64 && event.keyCode < 91) { // Only trigger on letters
            CodeMirror.commands.autocomplete(cm, null, {completeSingle: false});
        }
    });
    
    // Refresh CodeMirror when tab is shown to fix rendering issues
    sqlTabBtn.addEventListener('shown.bs.tab', function () {
        editor.refresh();
    });

    // --- Tab Management ---

    function openTableTab(tableName) {
        // If tab exists, switch to it
        if (state.openTabs[tableName]) {
            const tabBtn = document.getElementById(`tab-${tableName}`);
            const tab = new bootstrap.Tab(tabBtn);
            tab.show();
            return;
        }

        // Initialize state
        state.openTabs[tableName] = {
            offset: 0,
            limit: 50,
            intervalId: null,
            monitor: false
        };

        // Create Tab Button
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.role = 'presentation';
        li.innerHTML = `
            <button class="nav-link" id="tab-${tableName}" data-bs-toggle="tab" data-bs-target="#content-${tableName}" type="button" role="tab">
                ${tableName}
                <span class="close-tab" onclick="event.stopPropagation(); closeTab('${tableName}')">&times;</span>
            </button>
        `;
        // Insert before SQL tab (last child)
        mainTabs.insertBefore(li, mainTabs.lastElementChild);

        // Create Tab Content
        const div = document.createElement('div');
        div.className = 'tab-pane fade';
        div.id = `content-${tableName}`;
        div.role = 'tabpanel';
        div.innerHTML = `
            <div class="mb-3 d-flex justify-content-between align-items-center bg-light p-2 rounded">
                <div class="d-flex align-items-center gap-3">
                    <h5 class="mb-0 text-primary">${tableName}</h5>
                    <div class="form-check form-switch mb-0" title="Auto-refresh every 3 seconds">
                        <input class="form-check-input" type="checkbox" id="monitor-${tableName}">
                        <label class="form-check-label" for="monitor-${tableName}">Monitor</label>
                    </div>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-secondary" onclick="refreshTab('${tableName}')">Refresh</button>
                </div>
            </div>
            <div class="table-responsive" id="data-${tableName}">
                <div class="p-3">Loading data...</div>
            </div>
            <nav aria-label="Page navigation" id="pagination-${tableName}" style="display: none;">
                <ul class="pagination justify-content-center mt-3">
                    <li class="page-item"><a class="page-link" href="#" onclick="changePage('${tableName}', -1)">Previous</a></li>
                    <li class="page-item disabled"><span class="page-link" id="page-info-${tableName}">Page 1</span></li>
                    <li class="page-item"><a class="page-link" href="#" onclick="changePage('${tableName}', 1)">Next</a></li>
                </ul>
            </nav>
        `;
        tabContent.appendChild(div);

        // Bind Monitor Event
        const monitorCheck = div.querySelector(`#monitor-${tableName}`);
        monitorCheck.addEventListener('change', (e) => {
            toggleMonitor(tableName, e.target.checked);
        });

        // Activate Tab
        const tabBtn = document.getElementById(`tab-${tableName}`);
        const tab = new bootstrap.Tab(tabBtn);
        tab.show();

        // Fetch Data
        fetchTableData(tableName);
    }

    window.closeTab = function(tableName) {
        // Clear interval
        if (state.openTabs[tableName].intervalId) {
            clearInterval(state.openTabs[tableName].intervalId);
        }
        delete state.openTabs[tableName];

        // Remove DOM
        const tabBtn = document.getElementById(`tab-${tableName}`);
        const tabContentDiv = document.getElementById(`content-${tableName}`);
        
        if (tabBtn) tabBtn.parentElement.remove();
        if (tabContentDiv) tabContentDiv.remove();

        // Switch to SQL tab
        const sqlTab = new bootstrap.Tab(sqlTabBtn);
        sqlTab.show();
    };

    window.refreshTab = function(tableName) {
        // If monitoring, we might need to pull first
        // But simple refresh usually implies re-reading local. 
        // User asked for "Monitor" which implies syncing.
        // Let's make "Refresh" also try to pull if possible, or just read local?
        // To be safe and consistent with "Monitor", Refresh should probably just read local, 
        // but Monitor does the Pull. 
        // Actually, manual Refresh is often used when user knows data changed.
        // Let's make Refresh do a Pull first if we have context.
        pullAndFetch(tableName);
    };

    window.changePage = function(tableName, direction) {
        const tabState = state.openTabs[tableName];
        if (!tabState) return;

        if (direction === -1 && tabState.offset > 0) {
            tabState.offset -= tabState.limit;
        } else if (direction === 1) {
            tabState.offset += tabState.limit;
        }
        fetchTableData(tableName); // Don't pull on page change, just read
    };

    function toggleMonitor(tableName, enabled) {
        const tabState = state.openTabs[tableName];
        if (!tabState) return;

        tabState.monitor = enabled;
        if (enabled) {
            // Initial pull
            pullAndFetch(tableName);
            // Poll
            tabState.intervalId = setInterval(() => {
                pullAndFetch(tableName);
            }, 3000);
        } else {
            if (tabState.intervalId) {
                clearInterval(tabState.intervalId);
                tabState.intervalId = null;
            }
        }
    }

    async function pullAndFetch(tableName) {
        // Silent pull
        try {
            // We need to know original dbName. 
            // We only have token. But wait, pulling requires deviceId, package, dbName.
            // We stored deviceId and package in state. But dbName?
            // Problem: We don't have dbName easily mapped from tableName or token.
            // Solution: We need to store currentDbName in state when we open a DB.
            if (state.currentDbName) {
                await fetch('/api/pull', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        device_id: state.deviceId,
                        package_name: state.package,
                        db_name: state.currentDbName
                    })
                });
            }
            // After pull (or fail), fetch data
            fetchTableData(tableName);
        } catch (e) {
            console.error("Auto-refresh pull failed", e);
        }
    }

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

    async function fetchPackages(deviceId, filter='all') {
        packageList.innerHTML = '<div class="p-2">Loading packages...</div>';
        try {
            const res = await fetch(`/api/packages/${deviceId}?filter=${filter}`);
            // The backend now returns a list of objects {name: '...', debuggable: null}
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
        state.currentDbName = dbName; // Store for auto-refresh
        
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
            
            // Populate autocomplete hints
            const hintTables = {};
            // Fetch columns for each table to improve hints
            // Note: This might be heavy if there are many tables. 
            // We can do it lazily or just for top tables. 
            // For now, let's just add table names.
            tables.forEach(t => {
                hintTables[t] = [];
            });
            
            // Update editor hints
            editor.setOption("hintOptions", {
                tables: hintTables
            });
            
            // Try to fetch columns for better autocomplete (in background)
            tables.forEach(async t => {
                try {
                    // Reuse the existing table data endpoint with limit=1 to get columns quickly
                    const res = await fetch(`/api/table/${token}/${t}?limit=1`);
                    const data = await res.json();
                    if (data.columns) {
                        hintTables[t] = data.columns;
                        // Update hints again with columns
                        editor.setOption("hintOptions", {
                            tables: hintTables
                        });
                    }
                } catch(ignore) {}
            });

        } catch (e) {
            tableList.innerHTML = '<div class="text-danger p-2">Error loading tables</div>';
        }
    }

    async function fetchTableData(tableName) {
        const tabState = state.openTabs[tableName];
        if (!tabState) return;

        const container = document.getElementById(`data-${tableName}`);
        // Only show loading if not monitoring (to avoid flicker)
        if (!tabState.monitor) {
           // container.innerHTML = '<div class="p-3">Loading data...</div>';
        }
        
        try {
            const res = await fetch(`/api/table/${state.dbToken}/${tableName}?limit=${tabState.limit}&offset=${tabState.offset}`);
            const data = await res.json();
            renderTableData(data.columns, data.rows, container);
            updatePagination(tableName, data.total);
        } catch (e) {
            container.innerHTML = '<div class="text-danger p-3">Error loading data</div>';
        }
    }

    async function executeQuery() {
        if (!state.dbToken) {
            alert('Please select a database first.');
            return;
        }
        
        const query = editor.getValue();
        // Don't clear previous result immediately, maybe? 
        // Or we use the history as the main display.
        // Let's clear the "current result" container but add to history.
        queryResultContainer.innerHTML = '<div class="p-3">Executing...</div>';
        
        const startTime = new Date();

        try {
            const res = await fetch(`/api/query/${state.dbToken}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query})
            });
            const data = await res.json();
            
            // Clear the temporary "Executing..." message
            queryResultContainer.innerHTML = '';

            // Add to history
            addQueryHistory(query, startTime, data);

        } catch (e) {
            queryResultContainer.innerHTML = '<div class="text-danger p-3">Error executing query</div>';
        }
    }

    function addQueryHistory(query, startTime, data) {
        historyCount++;
        const id = `history-${historyCount}`;
        const timeStr = startTime.toLocaleTimeString();
        const shortQuery = query.length > 50 ? query.substring(0, 50) + '...' : query;
        let statusClass = 'text-success';
        let statusText = 'Success';
        
        if (data.error) {
            statusClass = 'text-danger';
            statusText = 'Error';
        }

        const item = document.createElement('div');
        item.className = 'accordion-item';
        item.innerHTML = `
            <h2 class="accordion-header" id="heading-${id}">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-${id}" aria-expanded="false" aria-controls="collapse-${id}">
                    <div class="d-flex w-100 justify-content-between me-3">
                        <span><strong>#${historyCount}</strong> [${timeStr}] <span class="text-muted ms-2">${shortQuery}</span></span>
                        <span class="${statusClass}">${statusText}</span>
                    </div>
                </button>
            </h2>
            <div id="collapse-${id}" class="accordion-collapse collapse show" aria-labelledby="heading-${id}" data-bs-parent="#query-history">
                <div class="accordion-body">
                    <div class="mb-2"><small class="text-muted">Full Query:</small> <pre class="bg-light p-2">${query}</pre></div>
                    <div id="result-${id}" class="table-responsive"></div>
                </div>
            </div>
        `;
        
        // Prepend to history
        queryHistoryContainer.insertBefore(item, queryHistoryContainer.firstChild);

        // Render result inside the accordion body
        const resultContainer = item.querySelector(`#result-${id}`);
        if (data.error) {
            resultContainer.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
        } else if (data.message) {
            resultContainer.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
        } else {
            renderTableData(data.columns, data.rows, resultContainer);
        }
        
        // Keep history size manageable (e.g. max 10)
        if (queryHistoryContainer.children.length > 10) {
            queryHistoryContainer.lastElementChild.remove();
        }
    }

    // --- Render Helpers ---

    let allPackages = [];
    function renderPackages(packages) {
        // packages is list of {name, debuggable}
        allPackages = packages;
        filterPackages();
    }

    function filterPackages() {
        const term = packageSearch.value.toLowerCase();
        const onlyDebug = document.getElementById('filter-debug').checked;

        const filtered = allPackages.filter(p => {
            const matchesTerm = p.name.toLowerCase().includes(term);
            const matchesDebug = onlyDebug ? p.debuggable === true : true;
            return matchesTerm && matchesDebug;
        });
        
        packageList.innerHTML = '';
        
        // Optimization: Only render first 100 to keep DOM light
        const toRender = filtered.slice(0, 100);
        
        toRender.forEach(p => {
            const item = document.createElement('a');
            item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
            item.id = `pkg-${p.name}`;
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = p.name;
            item.appendChild(nameSpan);
            
            // Badge placeholder
            const badge = document.createElement('span');
            badge.className = 'badge rounded-pill bg-secondary';
            badge.style.display = 'none'; // Hide initially
            badge.textContent = '...';
            item.appendChild(badge);

            item.onclick = () => {
                // Highlight
                document.querySelectorAll('#package-list .active').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                
                state.package = p.name;
                fetchDatabases(state.deviceId, p.name);
            };
            packageList.appendChild(item);
            
            // Trigger check if not known
            if (p.debuggable === null) {
                // Check status
                fetch(`/api/package-debuggable/${state.deviceId}/${p.name}`)
                    .then(res => res.json())
                    .then(data => {
                        p.debuggable = data.debuggable;
                        updatePackageBadge(badge, data.debuggable);
                    });
            } else {
                updatePackageBadge(badge, p.debuggable);
            }
        });
    }
    
    function updatePackageBadge(badge, isDebuggable) {
        if (isDebuggable) {
            badge.className = 'badge rounded-pill bg-success';
            badge.innerHTML = '🐛 Debug';
            badge.style.display = 'inline-block';
            badge.title = 'Debuggable (Accessible without Root)';
        } else {
            // Optional: Show "Release" or nothing
            // badge.className = 'badge rounded-pill bg-light text-dark';
            // badge.textContent = 'Rel';
            badge.style.display = 'none';
        }
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
                openTableTab(t);
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

    function updatePagination(tableName, total) {
        const tabState = state.openTabs[tableName];
        const pagination = document.getElementById(`pagination-${tableName}`);
        const pageInfo = document.getElementById(`page-info-${tableName}`);
        const prevPage = pagination.querySelector('li:first-child');
        const nextPage = pagination.querySelector('li:last-child');

        if (total > tabState.limit) {
            pagination.style.display = 'block';
            const currentPage = Math.floor(tabState.offset / tabState.limit) + 1;
            pageInfo.textContent = `Page ${currentPage} (Total: ${total})`;
            
            prevPage.classList.toggle('disabled', tabState.offset === 0);
            nextPage.classList.toggle('disabled', tabState.offset + tabState.limit >= total);
        } else {
            pagination.style.display = 'none';
        }
    }

    // --- Event Listeners ---

    refreshDevicesBtn.onclick = fetchDevices;

    // Filter Listeners
    document.querySelectorAll('input[name="pkg-filter"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (state.deviceId) {
                fetchPackages(state.deviceId, e.target.value);
            }
        });
    });

    const filterDebug = document.getElementById('filter-debug');
    filterDebug.addEventListener('change', () => {
        filterPackages(); // Re-filter on client side
    });

    deviceSelect.onchange = () => {
        const selected = deviceSelect.options[deviceSelect.selectedIndex];
        state.deviceId = selected.value;
        const isRoot = selected.dataset.root === 'true'; 
        
        if (state.deviceId) {
            // Update UI for non-root but run-as support
            if (isRoot) {
                rootStatus.textContent = '✅ Rooted';
                rootStatus.className = 'mt-1 small text-success';
                // Reset filter to All when changing device
                document.getElementById('filter-all').checked = true;
                fetchPackages(state.deviceId);
            } else {
                rootStatus.textContent = '⚠️ Not Rooted (Only debuggable apps supported)';
                rootStatus.className = 'mt-1 small text-warning';
                document.getElementById('filter-all').checked = true;
                fetchPackages(state.deviceId); // Try to list packages anyway
            }
        } else {
            rootStatus.textContent = '';
            packageList.innerHTML = '';
        }
        
        // Reset downstream
        dbCard.style.display = 'none';
        tableCard.style.display = 'none';
        // Close all table tabs? Maybe not strictly necessary but cleaner
        state.package = null;
        state.dbToken = null;
    };

    packageSearch.onkeyup = filterPackages;

    runQueryBtn.onclick = executeQuery;

    // Initial load
    fetchDevices();
});
