document.addEventListener("DOMContentLoaded", function() {
    const intro = document.querySelector('.intro-container');
    if (intro) {
        setTimeout(() => {
            intro.classList.add('show');
        }, 500);
    }
});