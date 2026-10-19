/**
 * Online Attendance Tracking System - Core JavaScript
 * Modern, Accessible & Responsive Interactions
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Initialize Bootstrap tooltips with container body for overflow avoidance
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, { container: 'body' });
    });

    // 2. Auto-dismiss flash alert messages after 6 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 6000);
    });

    // 3. Mobile Sidebar Navigation Toggle & Accessibility State
    const sidebarToggleBtn = document.getElementById('sidebarToggle');
    const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    function openSidebar() {
        document.body.classList.add('sidebar-open');
        if (sidebarToggleBtn) {
            sidebarToggleBtn.setAttribute('aria-expanded', 'true');
        }
        if (sidebarCloseBtn) {
            sidebarCloseBtn.focus();
        }
    }

    function closeSidebar() {
        document.body.classList.remove('sidebar-open');
        if (sidebarToggleBtn) {
            sidebarToggleBtn.setAttribute('aria-expanded', 'false');
            sidebarToggleBtn.focus();
        }
    }

    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (document.body.classList.contains('sidebar-open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
    }

    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', function (e) {
            e.preventDefault();
            closeSidebar();
        });
    }

    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', function () {
            closeSidebar();
        });
    }

    // Close mobile sidebar on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && document.body.classList.contains('sidebar-open')) {
            closeSidebar();
        }
    });

    // Automatically close sidebar if window resized to desktop (>= 992px)
    window.addEventListener('resize', function () {
        if (window.innerWidth >= 992 && document.body.classList.contains('sidebar-open')) {
            document.body.classList.remove('sidebar-open');
            if (sidebarToggleBtn) {
                sidebarToggleBtn.setAttribute('aria-expanded', 'false');
            }
        }
    });

    // 4. Password Show / Hide toggle functionality
    const togglePasswordBtn = document.getElementById('togglePasswordBtn');
    const passwordInput = document.getElementById('loginPassword');
    const togglePasswordIcon = document.getElementById('togglePasswordIcon');

    if (togglePasswordBtn && passwordInput && togglePasswordIcon) {
        togglePasswordBtn.addEventListener('click', function () {
            const isPassword = passwordInput.type === 'password';
            passwordInput.type = isPassword ? 'text' : 'password';
            togglePasswordIcon.classList.toggle('bi-eye', !isPassword);
            togglePasswordIcon.classList.toggle('bi-eye-slash', isPassword);
            togglePasswordBtn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
        });
    }

    // 5. Select all checkboxes utility for bulk selection tables
    const selectAllCheckbox = document.getElementById('selectAllAttendance');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            const checkboxes = document.querySelectorAll('.attendance-checkbox');
            checkboxes.forEach(cb => cb.checked = selectAllCheckbox.checked);
        });
    }

    // 6. Automatic submit for date picker inputs with class .auto-submit-date
    const autoSubmitDateInputs = document.querySelectorAll('.auto-submit-date');
    autoSubmitDateInputs.forEach(input => {
        input.addEventListener('change', function () {
            if (this.form) {
                this.form.submit();
            }
        });
    });

    // 7. Form Loading States: Prevent double-click submission and show spinner
    const formsWithSubmit = document.querySelectorAll('form:not([data-no-loading])');
    formsWithSubmit.forEach(form => {
        form.addEventListener('submit', function (e) {
            // Check form validity if HTML5 validation is active
            if (form.checkValidity && !form.checkValidity()) {
                return;
            }
            const submitBtn = form.querySelector('button[type="submit"]:not([data-no-loading])');
            if (submitBtn && !submitBtn.disabled) {
                const originalHtml = submitBtn.innerHTML;
                submitBtn.dataset.originalHtml = originalHtml;
                // Defer disabling slightly to allow standard form submission to register
                setTimeout(() => {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
                }, 10);
            }
        });
    });
});
