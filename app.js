// Navigation
function switchSection(sectionName) {
    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.section === sectionName) {
            item.classList.add('active');
        }
    });

    // Update active section
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionName).classList.add('active');

    // Update title
    const titles = {
        'dashboard': 'Dashboard',
        'niches': 'Manage Niches',
        'posts': 'Manage Posts',
        'schedule': 'Posting Schedules',
        'accounts': 'Platform Accounts',
        'scheduler': 'Scheduler Control'
    };
    document.getElementById('section-title').textContent = titles[sectionName];

    // Load data for the section
    loadSectionData(sectionName);
}

// Toggle form visibility
function toggleForm(formId) {
    const form = document.getElementById(formId);
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

// Load section data
function loadSectionData(section) {
    switch (section) {
        case 'dashboard':
            loadDashboardStats();
            break;
        case 'niches':
            loadNiches();
            break;
        case 'posts':
            loadPosts();
            break;
        case 'schedule':
            loadSchedules();
            break;
        case 'accounts':
            loadAccounts();
            break;
    }
}

// Dashboard Stats
async function loadDashboardStats() {
    try {
        const [niches, posts, scheduledPosts, accounts] = await Promise.all([
            fetch('/api/niches').then(r => r.json()),
            fetch('/api/posts').then(r => r.json()),
            fetch('/api/posts/scheduled').then(r => r.json()),
            fetch('/api/accounts').then(r => r.json())
        ]);

        document.getElementById('total-niches').textContent = niches.length || 0;
        document.getElementById('total-posts').textContent = posts.length || 0;
        document.getElementById('scheduled-posts').textContent = scheduledPosts.length || 0;
        document.getElementById('total-accounts').textContent = accounts ? 1 : 0;
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
    }
}

// Niches
async function loadNiches() {
    try {
        const response = await fetch('/api/niches');
        const niches = await response.json();
        const tbody = document.getElementById('niches-table');

        tbody.innerHTML = niches.map(niche => `
            <tr>
                <td>${niche.id}</td>
                <td>${niche.name}</td>
                <td>${niche.description}</td>
                <td>${niche.primary_statement}</td>
                <td>${new Date(niche.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading niches:', error);
    }
}

async function createNiche(event) {
    event.preventDefault();

    const data = {
        name: document.getElementById('niche-name').value,
        description: document.getElementById('niche-description').value,
        primary_statement: document.getElementById('niche-statement').value
    };

    try {
        const response = await fetch('/api/niches', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            alert('Niche created successfully!');
            event.target.reset();
            toggleForm('niche-form');
            loadNiches();
        } else {
            alert('Error creating niche');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating niche');
    }
}

// Posts
async function loadPosts() {
    try {
        const response = await fetch('/api/posts');
        const posts = await response.json();
        const tbody = document.getElementById('posts-table');

        tbody.innerHTML = posts.map(post => `
            <tr>
                <td>${post.id}</td>
                <td>${post.niche_id}</td>
                <td>${post.content.substring(0, 50)}...</td>
                <td><span class="badge">${post.status}</span></td>
                <td>${post.scheduled_time ? new Date(post.scheduled_time).toLocaleString() : 'N/A'}</td>
                <td>${new Date(post.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading posts:', error);
    }
}

async function loadScheduledPosts() {
    try {
        const response = await fetch('/api/posts/scheduled');
        const posts = await response.json();
        const tbody = document.getElementById('posts-table');

        tbody.innerHTML = posts.map(post => `
            <tr>
                <td>${post.id}</td>
                <td>${post.niche_id}</td>
                <td>${post.content.substring(0, 50)}...</td>
                <td><span class="badge">${post.status}</span></td>
                <td>${new Date(post.scheduled_time).toLocaleString()}</td>
                <td>${new Date(post.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading scheduled posts:', error);
    }
}

async function createPost(event) {
    event.preventDefault();

    const data = {
        niche_id: parseInt(document.getElementById('post-niche-id').value),
        account_id: parseInt(document.getElementById('post-account-id').value),
        content: document.getElementById('post-content').value,
        media_url: document.getElementById('post-media-url').value || null,
        scheduled_time: document.getElementById('post-scheduled-time').value || null,
        status: document.getElementById('post-status').value
    };

    try {
        const response = await fetch('/api/posts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            alert('Post created successfully!');
            event.target.reset();
            toggleForm('post-form');
            loadPosts();
        } else {
            alert('Error creating post');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating post');
    }
}

// Schedules
async function loadSchedules() {
    try {
        const response = await fetch('/api/schedules');
        const schedules = await response.json();
        const tbody = document.getElementById('schedule-table');

        tbody.innerHTML = schedules.map(schedule => `
            <tr>
                <td>${schedule.id}</td>
                <td>${schedule.niche_id}</td>
                <td>${schedule.posts_per_day}</td>
                <td>${schedule.needs_approval ? 'Yes' : 'No'}</td>
                <td>${new Date(schedule.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading schedules:', error);
    }
}

async function createSchedule(event) {
    event.preventDefault();

    const data = {
        niche_id: parseInt(document.getElementById('schedule-niche-id').value),
        posts_per_day: parseInt(document.getElementById('schedule-posts-per-day').value),
        needs_approval: parseInt(document.getElementById('schedule-needs-approval').value)
    };

    try {
        const response = await fetch('/api/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            alert('Schedule created successfully!');
            event.target.reset();
            toggleForm('schedule-form');
            loadSchedules();
        } else {
            alert('Error creating schedule');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating schedule');
    }
}

// Accounts
async function loadAccounts() {
    try {
        const response = await fetch('/api/accounts');
        const account = await response.json();
        const tbody = document.getElementById('accounts-table');

        if (account) {
            tbody.innerHTML = `
                <tr>
                    <td>${account.id}</td>
                    <td>${account.platform}</td>
                    <td>${account.api_key.substring(0, 20)}...</td>
                    <td>${new Date(account.created_at).toLocaleDateString()}</td>
                </tr>
            `;
        } else {
            tbody.innerHTML = '<tr><td colspan="4">No accounts configured</td></tr>';
        }
    } catch (error) {
        console.error('Error loading accounts:', error);
    }
}

async function createAccount(event) {
    event.preventDefault();

    const data = {
        platform: document.getElementById('account-platform').value,
        api_key: document.getElementById('account-api-key').value,
        api_secret: document.getElementById('account-api-secret').value,
        access_token: document.getElementById('account-access-token').value,
        access_secret: document.getElementById('account-access-secret').value
    };

    try {
        const response = await fetch('/api/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            alert('Account created successfully!');
            event.target.reset();
            toggleForm('account-form');
            loadAccounts();
        } else {
            alert('Error creating account');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating account');
    }
}

// Scheduler Controls
async function assignPosts() {
    showLoading('assign-result');
    try {
        const response = await fetch('/run-assign-posts');
        const data = await response.json();

        const resultDiv = document.getElementById('assign-result');
        resultDiv.className = `result-message ${data.status}`;
        resultDiv.textContent = data.message;
    } catch (error) {
        showError('assign-result', error.message);
    }
}

async function processDuePosts() {
    showLoading('process-result');
    try {
        const response = await fetch('/run-due-posts');
        const data = await response.json();

        const resultDiv = document.getElementById('process-result');
        resultDiv.className = `result-message ${data.status}`;
        resultDiv.textContent = data.message;
    } catch (error) {
        showError('process-result', error.message);
    }
}

async function startScheduler() {
    showLoading('scheduler-result');
    try {
        const response = await fetch('/start-scheduler');
        const data = await response.json();

        const resultDiv = document.getElementById('scheduler-result');
        resultDiv.className = `result-message ${data.status}`;
        resultDiv.textContent = data.message;
    } catch (error) {
        showError('scheduler-result', error.message);
    }
}

function showLoading(elementId) {
    const div = document.getElementById(elementId);
    div.className = 'result-message';
    div.textContent = 'Loading...';
    div.style.display = 'block';
}

function showError(elementId, message) {
    const div = document.getElementById(elementId);
    div.className = 'result-message error';
    div.textContent = `Error: ${message}`;
    div.style.display = 'block';
}

// Initialize navigation
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        switchSection(item.dataset.section);
    });
});

// Load dashboard on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
});
