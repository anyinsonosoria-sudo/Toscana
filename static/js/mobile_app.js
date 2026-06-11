/* ==========================================================================
   Mobile App (PWA) JS Optimizations
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Setup Page Transitions
    setupPageTransitions();
    
    // 2. Setup Haptic Feedback on bottom nav
    setupHaptics();
    
    // 3. Setup PWA Install Prompt
    setupPwaInstallPrompt();
});

function setupPageTransitions() {
    // Create transition overlay if it doesn't exist
    let overlay = document.getElementById('pwa-page-transition');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'pwa-page-transition';
        overlay.innerHTML = '<div class="pwa-spinner"></div>';
        document.body.appendChild(overlay);
    }
    
    // Hide overlay on pageshow (e.g., when returning via back button)
    window.addEventListener('pageshow', (e) => {
        overlay.classList.remove('active');
    });

    // Attach to internal links (especially bottom nav)
    const links = document.querySelectorAll('a:not([target="_blank"]):not([href^="#"]):not([href^="mailto:"]):not([href^="tel:"])');
    links.forEach(link => {
        link.addEventListener('click', (e) => {
            // Only trigger if it's not a modifier click
            if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.button !== 0) return;
            
            const href = link.getAttribute('href');
            if (href && href !== '#' && !href.includes('javascript:')) {
                overlay.classList.add('active');
                // Failsafe: if navigation fails or takes too long, hide overlay after 5s
                setTimeout(() => overlay.classList.remove('active'), 5000);
            }
        });
    });
}

function setupHaptics() {
    const navItems = document.querySelectorAll('.resident-bottom-nav__item, .btn');
    navItems.forEach(item => {
        item.addEventListener('touchstart', () => {
            if (navigator.vibrate) {
                // Short, subtle vibration
                navigator.vibrate(15);
            }
        }, { passive: true });
    });
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

    // Only show if the browser fires beforeinstallprompt
    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent Chrome 67 and earlier from automatically showing the prompt
        e.preventDefault();
        // Stash the event so it can be triggered later.
        deferredPrompt = e;
        
        // Show the banner if user hasn't dismissed it recently
        if (!localStorage.getItem('pwa-prompt-dismissed')) {
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
    
    if (isIos() && !isStandalone && !localStorage.getItem('pwa-prompt-dismissed')) {
        // Change text for iOS instructions
        banner.querySelector('.pwa-install-btn').style.display = 'none';
        banner.querySelector('.pwa-install-banner__text').innerHTML = 'Toca el botón <i class="bi bi-box-arrow-up"></i> Compartir y selecciona <strong>"Agregar a Inicio"</strong>.';
        setTimeout(() => banner.classList.add('show'), 2000);
    }
}
