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