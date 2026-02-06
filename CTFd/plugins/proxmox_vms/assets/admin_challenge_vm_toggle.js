(function() {
    // Only run on challenge edit pages
    if (typeof CHALLENGE_ID === 'undefined') return;

    var csrfNonce = init.csrfNonce;
    var container = document.getElementById('challenge-update-container');
    if (!container) return;

    // Build the toggle card
    var card = document.createElement('div');
    card.className = 'card mt-3';
    card.innerHTML =
        '<div class="card-header"><h5 class="mb-0"><i class="fas fa-server"></i> Proxmox VM</h5></div>' +
        '<div class="card-body">' +
            '<p class="text-muted small mb-2">When enabled, users will see a VM control panel on this challenge.</p>' +
            '<div class="custom-control custom-switch">' +
                '<input type="checkbox" class="custom-control-input" id="proxmox-vm-toggle">' +
                '<label class="custom-control-label" for="proxmox-vm-toggle">Enable VM for this challenge</label>' +
            '</div>' +
            '<div id="proxmox-vm-status" class="mt-2 small"></div>' +
        '</div>';
    container.appendChild(card);

    var toggle = document.getElementById('proxmox-vm-toggle');
    var statusEl = document.getElementById('proxmox-vm-status');

    // Load current state
    fetch('/proxmox/admin/challenges', {
        headers: { 'CSRF-Token': csrfNonce }
    })
    .then(function(r) { return r.json(); })
    .then(function(r) {
        if (!r.success) return;
        for (var i = 0; i < r.challenges.length; i++) {
            if (r.challenges[i].id === CHALLENGE_ID) {
                toggle.checked = r.challenges[i].vm_enabled;
                break;
            }
        }
    });

    // Handle toggle
    toggle.addEventListener('change', function() {
        var enabled = toggle.checked;
        fetch('/proxmox/admin/challenges/' + CHALLENGE_ID + '/vm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'CSRF-Token': csrfNonce
            },
            body: JSON.stringify({ enabled: enabled })
        })
        .then(function(r) { return r.json(); })
        .then(function(r) {
            if (r.success) {
                statusEl.innerHTML = '<span class="text-success">Saved.</span>';
            } else {
                statusEl.innerHTML = '<span class="text-danger">Failed to save.</span>';
                toggle.checked = !enabled;
            }
            setTimeout(function() { statusEl.innerHTML = ''; }, 3000);
        })
        .catch(function() {
            statusEl.innerHTML = '<span class="text-danger">Request failed.</span>';
            toggle.checked = !enabled;
            setTimeout(function() { statusEl.innerHTML = ''; }, 3000);
        });
    });
})();
