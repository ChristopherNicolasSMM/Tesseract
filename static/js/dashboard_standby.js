/* Visual inactivity only; no requests or changes to brewing controls. */
(function (global) {
  'use strict';
  global.TesseractDashboardStandby = {
    mount: function (options) {
      const canvas = options.canvas;
      if (!canvas || !options.enabled || !Number.isInteger(options.seconds) || options.seconds < 10 || options.seconds > 86400) return function () {};
      let timer = null;
      let disposed = false;
      function wake() {
        if (disposed) return;
        canvas.classList.remove('db-visual-standby');
        clearTimeout(timer);
        timer = setTimeout(function idle() {
          if (disposed || !canvas.isConnected) return;
          if (options.suspended && options.suspended()) { wake(); return; }
          canvas.classList.add('db-visual-standby');
        }, options.seconds * 1000);
      }
      const events = ['pointermove', 'pointerdown', 'keydown', 'focusin', 'wheel'];
      events.forEach(function (event) { document.addEventListener(event, wake, {passive: true}); });
      function visibility() { wake(); }
      document.addEventListener('visibilitychange', visibility);
      wake();
      return function () {
        disposed = true;
        clearTimeout(timer);
        canvas.classList.remove('db-visual-standby');
        events.forEach(function (event) { document.removeEventListener(event, wake); });
        document.removeEventListener('visibilitychange', visibility);
      };
    }
  };
})(window);
