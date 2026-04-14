// main.js — students will add JavaScript here as features are built

// Video Modal for "See how it works"
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('video-modal');
    const videoIframe = document.getElementById('modal-video');
    const closeBtn = document.querySelector('.modal-close');
    const videoTrigger = document.querySelector('.btn-secondary[href="#how-it-works"]');

    // YouTube video URL (placeholder - replace with actual video ID)
    const videoUrl = 'https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1';

    // Open modal
    if (videoTrigger) {
        videoTrigger.addEventListener('click', function(e) {
            e.preventDefault();
            modal.classList.add('active');
            videoIframe.src = videoUrl;
            document.body.style.overflow = 'hidden';
        });
    }

    // Close modal function
    function closeModal() {
        modal.classList.remove('active');
        videoIframe.src = '';
        document.body.style.overflow = '';
    }

    // Close on button click
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }

    // Close on overlay click (outside modal)
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeModal();
        }
    });
});
