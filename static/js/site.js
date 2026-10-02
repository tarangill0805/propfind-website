document.querySelectorAll('.flash').forEach((item) => setTimeout(() => item.remove(), 4500));
/* =========================
   PROPERTY PHOTO SLIDERS
========================= */

document.addEventListener("DOMContentLoaded", function () {

    const sliders = document.querySelectorAll(".property-slider");

    sliders.forEach(function (slider) {

        const slides = slider.querySelectorAll(".property-slide");
        const dots = slider.querySelectorAll(".slider-dot");

        const prev = slider.querySelector(".slider-prev");
        const next = slider.querySelector(".slider-next");

        if (slides.length <= 1) {
            return;
        }

        let current = 0;
        let timer;


        function showSlide(index) {

            slides[current].classList.remove("active");

            if (dots[current]) {
                dots[current].classList.remove("active");
            }

            current = (index + slides.length) % slides.length;

            slides[current].classList.add("active");

            if (dots[current]) {
                dots[current].classList.add("active");
            }
        }


        function startSlider() {

            timer = setInterval(function () {

                showSlide(current + 1);

            }, 3000); // 3 seconds

        }


        function resetSlider() {

            clearInterval(timer);

            startSlider();

        }


        if (next) {

            next.addEventListener("click", function (event) {

                event.preventDefault();
                event.stopPropagation();

                showSlide(current + 1);
                resetSlider();

            });

        }


        if (prev) {

            prev.addEventListener("click", function (event) {

                event.preventDefault();
                event.stopPropagation();

                showSlide(current - 1);
                resetSlider();

            });

        }


        dots.forEach(function (dot, index) {

            dot.addEventListener("click", function (event) {

                event.preventDefault();
                event.stopPropagation();

                showSlide(index);
                resetSlider();

            });

        });


        startSlider();

    });

});