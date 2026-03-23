/* ================================
   COR AMANS Main JavaScript File
================================ */


/* -------------------------------
   Hero Slideshow
--------------------------------*/

document.addEventListener("DOMContentLoaded", function () {

    const slides = document.querySelectorAll(".slide");
    let current = 0;

    function showSlide(index) {

        slides.forEach((slide) => {
            slide.classList.remove("active");
            slide.style.opacity = "0";
        });

        if (slides[index]) {
            slides[index].classList.add("active");
            slides[index].style.opacity = "1";
        }

    }

    function nextSlide() {
        current = (current + 1) % slides.length;
        showSlide(current);
    }

    if (slides.length > 0) {
        showSlide(current);
        setInterval(nextSlide, 5000);
    }

});


/* -------------------------------
   Scroll Trigger Animations
--------------------------------*/

document.addEventListener("DOMContentLoaded", function () {

    const observer = new IntersectionObserver((entries) => {

        entries.forEach((entry) => {

            if (entry.isIntersecting) {
                entry.target.classList.add("active");
            }

        });

    });

    const animatedElements = document.querySelectorAll(".scroll-animate");

    animatedElements.forEach((el) => {
        observer.observe(el);
    });

});

/* -------------------------------
   Navbar Scroll Effect
--------------------------------*/

document.addEventListener("DOMContentLoaded", function () {

    const navbar = document.getElementById("navbar");

    window.addEventListener("scroll", function () {

        if (window.scrollY > 50) {

            navbar.classList.add("bg-white", "shadow-md");
            navbar.classList.remove("bg-transparent");

        } else {

            navbar.classList.remove("bg-white", "shadow-md");
            navbar.classList.add("bg-transparent");

        }

    });

});


const navbar = document.getElementById('navbar');

window.addEventListener('scroll', () => {
    if(window.scrollY > 50){
        navbar.classList.add('bg-white/90', 'shadow-lg');
    } else {
        navbar.classList.remove('bg-white/90', 'shadow-lg');
    }
});

/* ================================
   COR AMANS Main JavaScript File
================================ */

// Wait for DOM to load
document.addEventListener("DOMContentLoaded", function() {
    
    /* -------------------------------
       Floating Notifications System
    ---------------------------------*/
    
    // Function to show floating notification
    window.showNotification = function(message, type = 'success', duration = 5000) {
        const container = document.getElementById('notification-container');
        if (!container) return;
        
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type} transform transition-all duration-500 ease-out translate-x-full opacity-0`;
        
        // Set icon based on type
        let icon = '';
        switch(type) {
            case 'success':
                icon = '<i class="fas fa-check-circle"></i>';
                break;
            case 'error':
                icon = '<i class="fas fa-exclamation-circle"></i>';
                break;
            case 'warning':
                icon = '<i class="fas fa-exclamation-triangle"></i>';
                break;
            case 'info':
                icon = '<i class="fas fa-info-circle"></i>';
                break;
            default:
                icon = '<i class="fas fa-bell"></i>';
        }
        
        // Set background color based on type
        let bgColor = '';
        switch(type) {
            case 'success':
                bgColor = 'bg-green-50 border-green-500 text-green-800';
                break;
            case 'error':
                bgColor = 'bg-red-50 border-red-500 text-red-800';
                break;
            case 'warning':
                bgColor = 'bg-yellow-50 border-yellow-500 text-yellow-800';
                break;
            case 'info':
                bgColor = 'bg-blue-50 border-blue-500 text-blue-800';
                break;
        }
        
        notification.innerHTML = `
            <div class="${bgColor} border-l-4 rounded-lg shadow-lg p-4 mb-3 relative overflow-hidden">
                <div class="flex items-start gap-3">
                    <div class="text-xl ${type === 'success' ? 'text-green-500' : type === 'error' ? 'text-red-500' : type === 'warning' ? 'text-yellow-500' : 'text-blue-500'}">
                        ${icon}
                    </div>
                    <div class="flex-1">
                        <p class="text-sm font-medium">${message}</p>
                    </div>
                    <button class="close-notification text-gray-400 hover:text-gray-600 transition">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="progress-bar absolute bottom-0 left-0 h-1 bg-${type === 'success' ? 'green' : type === 'error' ? 'red' : type === 'warning' ? 'yellow' : 'blue'}-500" style="width: 100%; animation: shrink ${duration/1000}s linear forwards;"></div>
            </div>
        `;
        
        container.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full', 'opacity-0');
            notification.classList.add('translate-x-0', 'opacity-100');
        }, 10);
        
        // Auto remove after duration
        const timeout = setTimeout(() => {
            removeNotification(notification);
        }, duration);
        
        // Close button functionality
        const closeBtn = notification.querySelector('.close-notification');
        closeBtn.addEventListener('click', () => {
            clearTimeout(timeout);
            removeNotification(notification);
        });
        
        // Remove function with animation
        function removeNotification(notif) {
            notif.classList.remove('translate-x-0', 'opacity-100');
            notif.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => {
                if (notif.parentNode) {
                    notif.remove();
                }
            }, 500);
        }
    };
    
    // Add CSS animation for progress bar
    const style = document.createElement('style');
    style.textContent = `
        @keyframes shrink {
            from { width: 100%; }
            to { width: 0%; }
        }
        
        .notification {
            transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .notification:hover {
            transform: translateX(-4px);
        }
    `;
    document.head.appendChild(style);
    
    /* -------------------------------
       Hero Slideshow
    ---------------------------------*/
    
    const slides = document.querySelectorAll(".slide");
    let current = 0;
    
    function showSlide(index) {
        slides.forEach((slide) => {
            slide.classList.remove("active");
            slide.style.opacity = "0";
        });
        
        if (slides[index]) {
            slides[index].classList.add("active");
            slides[index].style.opacity = "1";
        }
    }
    
    function nextSlide() {
        if (slides.length > 0) {
            current = (current + 1) % slides.length;
            showSlide(current);
        }
    }
    
    if (slides.length > 0) {
        showSlide(current);
        setInterval(nextSlide, 5000);
    }
    
    /* -------------------------------
       Scroll Trigger Animations
    ---------------------------------*/
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("active");
            }
        });
    }, { threshold: 0.1 });
    
    const animatedElements = document.querySelectorAll(".scroll-animate");
    animatedElements.forEach((el) => {
        observer.observe(el);
    });
    
    /* -------------------------------
       Navbar Scroll Effect
    ---------------------------------*/
    
    const navbar = document.getElementById("navbar");
    if (navbar) {
        window.addEventListener("scroll", function() {
            if (window.scrollY > 50) {
                navbar.classList.add("bg-white", "shadow-md");
                navbar.classList.remove("bg-white/70", "backdrop-blur-md");
            } else {
                navbar.classList.remove("bg-white", "shadow-md");
                navbar.classList.add("bg-white/70", "backdrop-blur-md");
            }
        });
    }
    
    /* -------------------------------
       Display Flash Messages as Notifications
    ---------------------------------*/
    
    // Convert Flask flash messages to floating notifications
    const flashMessages = document.querySelectorAll('.flash-message');
    if (flashMessages.length > 0) {
        flashMessages.forEach(msg => {
            const message = msg.getAttribute('data-message');
            const category = msg.getAttribute('data-category') || 'info';
            showNotification(message, category, 5000);
            msg.remove(); // Remove original flash message
        });
    }
});

/* -------------------------------
   Helper function to show notification from anywhere
--------------------------------*/

function notify(message, type = 'success', duration = 5000) {
    if (window.showNotification) {
        window.showNotification(message, type, duration);
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}