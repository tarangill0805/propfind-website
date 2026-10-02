
document.addEventListener("DOMContentLoaded", function () {

    /* =========================
       FLASH MESSAGES
    ========================= */

    document.querySelectorAll(".flash").forEach(function (item) {

        setTimeout(function () {
            item.remove();
        }, 4500);

    });


    /* =========================
       PROPERTY PHOTO SLIDERS
    ========================= */

    document.querySelectorAll(".property-slider").forEach(function (slider) {

        const slides = slider.querySelectorAll(".property-slide");
        const dots = slider.querySelectorAll(".slider-dot");
        const prev = slider.querySelector(".slider-prev");
        const next = slider.querySelector(".slider-next");

        if (slides.length <= 1) {
            return;
        }

        let current = 0;
        let timer = null;

        let startX = 0;
        let startY = 0;
        let moved = false;


        /* =========================
           SHOW SLIDE
        ========================= */

        function showSlide(index) {

            slides.forEach(function (slide) {
                slide.classList.remove("active");
            });

            dots.forEach(function (dot) {
                dot.classList.remove("active");
            });

            current =
                (index + slides.length) % slides.length;

            slides[current].classList.add("active");

            if (dots[current]) {
                dots[current].classList.add("active");
            }

        }


        /* =========================
           AUTO SLIDE - 1 SECOND
        ========================= */

        function startSlider() {

            clearInterval(timer);

            timer = setInterval(function () {

                showSlide(current + 1);

            }, 2000); // 2 seconds

        }


        function resetSlider() {

            clearInterval(timer);

            startSlider();

        }


        /* =========================
           NEXT
        ========================= */

        if (next) {

            next.addEventListener("click", function (event) {

                event.preventDefault();
                event.stopPropagation();

                showSlide(current + 1);

                resetSlider();

            });

        }


        /* =========================
           PREVIOUS
        ========================= */

        if (prev) {

            prev.addEventListener("click", function (event) {

                event.preventDefault();
                event.stopPropagation();

                showSlide(current - 1);

                resetSlider();

            });

        }


        /* =========================
           DOTS
        ========================= */

        dots.forEach(function (dot, index) {

            dot.addEventListener("click", function (event) {

                event.preventDefault();
                event.stopPropagation();

                showSlide(index);

                resetSlider();

            });

        });


        /* =========================
           MOBILE TOUCH
        ========================= */

        slider.addEventListener("touchstart", function (event) {

            if (!event.touches.length) {
                return;
            }

            startX = event.touches[0].clientX;
            startY = event.touches[0].clientY;

            moved = false;

            clearInterval(timer);

        }, { passive: true });


        slider.addEventListener("touchmove", function (event) {

            if (!event.touches.length) {
                return;
            }

            const currentX =
                event.touches[0].clientX;

            const currentY =
                event.touches[0].clientY;

            const differenceX =
                currentX - startX;

            const differenceY =
                currentY - startY;


            /* Only horizontal movement */

            if (
                Math.abs(differenceX) >
                Math.abs(differenceY)
            ) {

                if (Math.abs(differenceX) > 20) {

                    moved = true;

                    event.preventDefault();

                }

            }

        }, { passive: false });


        slider.addEventListener("touchend", function (event) {

            if (!event.changedTouches.length) {
                return;
            }

            const endX =
                event.changedTouches[0].clientX;

            const endY =
                event.changedTouches[0].clientY;

            const differenceX =
                endX - startX;

            const differenceY =
                endY - startY;


            /* Minimum swipe distance */

            if (
                Math.abs(differenceX) < 50 ||
                Math.abs(differenceX) <= Math.abs(differenceY)
            ) {

                startSlider();

                return;

            }


            /* Swipe LEFT */

            if (differenceX < 0) {

                showSlide(current + 1);

            }


            /* Swipe RIGHT */

            else {

                showSlide(current - 1);

            }


            resetSlider();


            /* Prevent link after swipe */

            if (moved) {

                slider.dataset.swiped = "true";

                setTimeout(function () {

                    slider.dataset.swiped = "false";

                }, 300);

            }

        }, { passive: true });


        /* =========================
           STOP LINK AFTER SWIPE
        ========================= */

        slider.addEventListener("click", function (event) {

            if (slider.dataset.swiped === "true") {

                event.preventDefault();
                event.stopPropagation();

            }

        });


        /* =========================
           START
        ========================= */

        startSlider();

    });

});