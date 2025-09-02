function setLoading(button, loading=true) {
    if (loading) {
        button.disabled = true;
        button.innerHTML = '<div class="loading w-5 h-5 border-2 border-white border-t-transparent rounded-full mx-auto"></div>';
    } else {
        button.disabled = false;
        button.innerHTML = 'Log In';
    }
}
<button onclick="logoutUser()" 
        class="absolute top-4 right-4 text-sm text-gray-600 hover:text-purple-600">
    🚪 Logout
</button>
async function logoutUser() {
    await fetch('http://localhost:5000/api/logout', { method: 'POST', credentials: 'include' });
    currentUser = null;
    hideElement('main-app');
    showElement('auth-screen');
}
