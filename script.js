/* ================================================
   LAURA DELAHUNT-DEVLIN CONSULTING
   JavaScript — Interactions & Animations
   ================================================ */

// ---------- NAV SCROLL EFFECT ----------
const nav = document.getElementById('nav');

window.addEventListener('scroll', () => {
  if (window.scrollY > 60) {
    nav.classList.add('scrolled');
  } else {
    nav.classList.remove('scrolled');
  }
}, { passive: true });

// ---------- MOBILE MENU ----------
const burger     = document.getElementById('burger');
const mobileMenu = document.getElementById('mobileMenu');
const menuClose  = document.getElementById('menuClose');
const mobileLinks = document.querySelectorAll('.mobile-link');

function openMenu() {
  mobileMenu.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeMenu() {
  mobileMenu.classList.remove('open');
  document.body.style.overflow = '';
}

burger.addEventListener('click', openMenu);
menuClose.addEventListener('click', closeMenu);
mobileLinks.forEach(link => link.addEventListener('click', closeMenu));

// ---------- SCROLL REVEAL ----------
const revealEls = document.querySelectorAll('.reveal, .reveal-left, .reveal-right');

const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      // Stagger siblings in same parent
      const siblings = Array.from(entry.target.parentElement.querySelectorAll(':scope > .reveal, :scope > .reveal-left, :scope > .reveal-right'));
      const idx = siblings.indexOf(entry.target);
      entry.target.style.transitionDelay = `${idx * 80}ms`;
      entry.target.classList.add('visible');
      revealObserver.unobserve(entry.target);
    }
  });
}, {
  threshold: 0.12,
  rootMargin: '0px 0px -60px 0px'
});

revealEls.forEach(el => revealObserver.observe(el));

// ---------- FOOTER YEAR ----------
document.getElementById('year').textContent = new Date().getFullYear();

// ---------- CONTACT FORM ----------
const form        = document.getElementById('contactForm');
const formSuccess = document.getElementById('formSuccess');

form.addEventListener('submit', (e) => {
  e.preventDefault();

  const name    = form.name.value.trim();
  const email   = form.email.value.trim();
  const message = form.message.value.trim();

  if (!name || !email || !message) {
    // Simple shake on invalid
    form.classList.add('shake');
    setTimeout(() => form.classList.remove('shake'), 600);
    return;
  }

  // Simulate a successful send (replace with real endpoint / EmailJS / Formspree)
  const btn = form.querySelector('.btn--full');
  btn.textContent = 'Sending…';
  btn.disabled = true;

  setTimeout(() => {
    form.reset();
    btn.textContent = 'Send Message';
    btn.disabled = false;
    formSuccess.style.display = 'block';
    setTimeout(() => { formSuccess.style.display = 'none'; }, 5000);
  }, 1200);
});

// ---------- SMOOTH SCROLL (fallback for older browsers) ----------
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});
