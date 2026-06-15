/* ==========================================================================
   Mobile App (PWA) JS Optimizations
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // 2. Setup Haptic Feedback on bottom nav
    setupHaptics();
    
    // 3. Setup PWA Install Prompt
    setupPwaInstallPrompt();
});

function setupHaptics() {
    // Safe haptic feedback using touchend to avoid canceling click events on Android
    document.addEventListener('touchend', (e) => {
        const target = e.target.closest('.btn, .nav-link, .resident-switcher__item, .resident-bottom-nav__item');
        if (target && navigator.vibrate) {
            navigator.vibrate(10); // Very light haptic tap
        }
    }, { passive: true });
}

function setupPwaInstallPrompt() {
    let deferredPrompt;
    
    // Check if already installed
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches 
                         || window.navigator.standalone 
                         || document.referrer.includes('android-app://');
    
    if (isStandalone) {
        document.body.classList.add('is-pwa');
        return; // Already installed
    }

    // Create the banner UI
    const banner = document.createElement('div');
    banner.className = 'pwa-install-banner';
    banner.innerHTML = `
        <div class="pwa-install-banner__icon"><i class="bi bi-app-indicator"></i></div>
        <div class="pwa-install-banner__content">
            <h4 class="pwa-install-banner__title">Instalar App Toscana</h4>
            <p class="pwa-install-banner__text">Añade la app a tu pantalla de inicio para acceso instantáneo.</p>
        </div>
        <button class="btn btn-sm btn-primary rounded-pill pwa-install-btn">Instalar</button>
        <button class="pwa-install-banner__close"><i class="bi bi-x-lg"></i></button>
    `;
    document.body.appendChild(banner);

    const installBtn = banner.querySelector('.pwa-install-btn');
    const closeBtn = banner.querySelector('.pwa-install-banner__close');

    // Helper to check if dismissed recently (7 days)
    const checkDismissed = () => {
        const dismissedAt = localStorage.getItem('pwa-prompt-dismissed');
        if (!dismissedAt) return false;
        const daysPassed = (Date.now() - parseInt(dismissedAt)) / (1000 * 60 * 60 * 24);
        return daysPassed < 7;
    };

    // Only show if the browser fires beforeinstallprompt
    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent Chrome 67 and earlier from automatically showing the prompt
        e.preventDefault();
        // Stash the event so it can be triggered later.
        deferredPrompt = e;
        
        // Show the banner if user hasn't dismissed it recently
        if (!checkDismissed()) {
            setTimeout(() => banner.classList.add('show'), 2000);
        }
    });

    installBtn.addEventListener('click', async () => {
        if (!deferredPrompt) return;
        banner.classList.remove('show');
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
            console.log('User accepted the install prompt');
        }
        deferredPrompt = null;
    });

    closeBtn.addEventListener('click', () => {
        banner.classList.remove('show');
        // Don't show again for a week
        localStorage.setItem('pwa-prompt-dismissed', Date.now().toString());
    });
    
    // iOS Safari fallback (doesn't support beforeinstallprompt)
    const isIos = () => {
      const userAgent = window.navigator.userAgent.toLowerCase();
      return /iphone|ipad|ipod/.test( userAgent );
    }
    
    if (isIos() && !isStandalone && !checkDismissed()) {
        // Change text for iOS instructions
        banner.querySelector('.pwa-install-btn').style.display = 'none';
        banner.querySelector('.pwa-install-banner__text').innerHTML = 'Toca el botón <i class="bi bi-box-arrow-up"></i> Compartir y selecciona <strong>"Agregar a Inicio"</strong>.';
        setTimeout(() => banner.classList.add('show'), 2000);
    }
}
