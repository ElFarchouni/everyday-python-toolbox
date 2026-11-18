/*
 * QR code generator - page logic.
 *
 * Reads the form, builds the text that goes inside the code, draws the live
 * preview and handles the downloads. The drawing itself is in qr-render.js.
 */
(function () {
  'use strict';

  var EXAMPLE = 'https://example.com';
  var NOTHING = { text: '', tip: '' };

  var logo = null;     // { src, width, height, image, name }
  var current = null;  // { model, real } - what the preview is showing
  var renderTimer = 0;
  var statusTimer = 0;

  function $(id) {
    return document.getElementById(id);
  }

  function val(id) {
    return $(id).value;
  }

  function chosen(name) {
    var el = document.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : '';
  }

  // ------------------------------------------------- what goes in the code

  // "example.com" -> "https://example.com"
  function withScheme(url) {
    url = url.trim();
    if (!url) return '';
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(url)) return url;
    if (/^(mailto|tel|sms|smsto|geo|bitcoin|magnet|market|spotify|tg|whatsapp|skype|facetime):/i.test(url)) return url;
    return 'https://' + url;
  }

  // "+212 (6) 12-34" -> "+21261234"   and   "00212..." -> "+212..."
  function phoneNumber(raw) {
    var s = raw.replace(/[^\d+]/g, '');
    if (s.indexOf('00') === 0) s = '+' + s.slice(2);
    return s.charAt(0) + s.slice(1).replace(/\+/g, '');
  }

  function escapeWifi(s) {
    return s.replace(/([\\;,:"])/g, '\\$1');
  }

  function escapeCard(s) {
    return s.replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/([;,])/g, '\\$1');
  }

  // One builder per type. Each returns the text for the code, plus an
  // optional tip shown under the form when something looks wrong.
  var builders = {
    link: function () {
      var url = withScheme(val('link-url'));
      var tip = '';
      if (/\s/.test(url)) {
        tip = 'A web address cannot contain spaces. Check for a typing mistake.';
      } else if (/^https?:\/\/[^./]+$/i.test(url)) {
        tip = 'This address looks incomplete. It usually ends with something like .com or .ma';
      }
      return { text: url, tip: tip };
    },

    text: function () {
      var text = val('text-body');
      return { text: text.trim() ? text : '', tip: '' };
    },

    wifi: function () {
      var name = val('wifi-ssid').trim();
      if (!name) return NOTHING;
      var security = val('wifi-sec');
      var password = val('wifi-pass');
      var text = 'WIFI:T:' + security + ';S:' + escapeWifi(name) + ';';
      if (security !== 'nopass') text += 'P:' + escapeWifi(password) + ';';
      if ($('wifi-hidden').checked) text += 'H:true;';
      text += ';';

      var tip = '';
      if (security !== 'nopass' && !password) {
        tip = 'Add the Wi-Fi password, or set Security to “None” if the network is open.';
      } else if (security === 'WPA' && password.length < 8) {
        tip = 'Wi-Fi passwords have at least 8 characters. Check that this one is complete.';
      }
      return { text: text, tip: tip };
    },

    contact: function () {
      var first = val('c-first').trim();
      var last = val('c-last').trim();
      var company = val('c-org').trim();
      var job = val('c-title').trim();
      var phone = phoneNumber(val('c-phone'));
      var email = val('c-email').trim();
      var website = withScheme(val('c-url'));

      if (!first && !last && !company) {
        var started = phone || email || job || website;
        return { text: '', tip: started ? 'Add a name so the contact can be saved.' : '' };
      }

      var lines = [
        'BEGIN:VCARD',
        'VERSION:3.0',
        'N:' + escapeCard(last) + ';' + escapeCard(first) + ';;;',
        'FN:' + escapeCard((first + ' ' + last).trim() || company)
      ];
      if (company) lines.push('ORG:' + escapeCard(company));
      if (job) lines.push('TITLE:' + escapeCard(job));
      if (phone) lines.push('TEL;TYPE=CELL:' + phone);
      if (email) lines.push('EMAIL:' + email);
      if (website) lines.push('URL:' + website);
      lines.push('END:VCARD');
      return { text: lines.join('\n'), tip: '' };
    },

    email: function () {
      var to = val('mail-to').trim();
      if (!to) return NOTHING;
      var subject = val('mail-subject').trim();
      var body = val('mail-body').trim();
      var extras = [];
      if (subject) extras.push('subject=' + encodeURIComponent(subject));
      if (body) extras.push('body=' + encodeURIComponent(body));
      return {
        text: 'mailto:' + to + (extras.length ? '?' + extras.join('&') : ''),
        tip: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to) ? '' : 'This email address looks incomplete.'
      };
    },

    phone: function () {
      var number = phoneNumber(val('tel-number'));
      if (!/\d/.test(number)) return NOTHING;
      return {
        text: 'tel:' + number,
        tip: number.charAt(0) === '+' ? '' :
          'Tip: start with the country code (like +212) so the number works from any country.'
      };
    },

    whatsapp: function () {
      var number = phoneNumber(val('wa-number'));
      var digits = number.replace('+', '');
      if (!digits) return NOTHING;
      var message = val('wa-text').trim();
      return {
        text: 'https://wa.me/' + digits + (message ? '?text=' + encodeURIComponent(message) : ''),
        tip: number.charAt(0) === '+' ? '' :
          'WhatsApp needs the full international number. Start with + and the country code, like +212 6 12 34 56 78.'
      };
    }
  };

  // ------------------------------------------------------ the chosen look

  function readStyle() {
    var gradient = chosen('fill') === 'gradient';
    return {
      shape: chosen('shape'),
      eye: chosen('eye'),
      fill: {
        type: gradient ? val('direction') : 'solid',
        color1: val('color1'),
        color2: val('color2')
      },
      background: $('bg-transparent').checked ? null : val('bg'),
      border: Number(val('border')),
      ecc: val('ecc'),
      logo: logo ? {
        src: logo.src,
        width: logo.width,
        height: logo.height,
        size: Number(val('logo-size')) / 100
      } : null
    };
  }

  // How bright a color looks, from 0 (black) to 1 (white).
  function brightness(hexColor) {
    var value = parseInt(hexColor.slice(1), 16);
    var parts = [value >> 16 & 255, value >> 8 & 255, value & 255];
    for (var i = 0; i < 3; i++) {
      var c = parts[i] / 255;
      parts[i] = c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    }
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2];
  }

  // Friendly warnings about anything that could stop the code from scanning.
  function findProblems(model) {
    var list = [];
    var colors = model.fill.type === 'solid'
      ? [model.fill.color1]
      : [model.fill.color1, model.fill.color2];
    var code = Math.max.apply(null, colors.map(brightness));
    var back = brightness(model.background || '#ffffff');

    if (code >= back) {
      list.push(['bad', 'The code is lighter than its background. Many phones cannot scan that. Use a dark code on a light background.']);
    } else if ((back + 0.05) / (code + 0.05) < 3) {
      list.push(['warn', 'The code and the background are close in color, so it may be hard to scan. Make the code darker.']);
    }
    if (!model.background) {
      list.push(['info', 'No background: place the code on a plain, light surface.']);
    }
    if (model.version >= 12) {
      list.push(['warn', 'That is a lot of content, so the squares are very small. Shorten it if you can, or print the code large.']);
    }
    if (model.eye === 'circle') {
      list.push(['info', 'Circle corners work with phone cameras, but some older scanner apps cannot read them. For printing, Square is the safest.']);
    }
    if (model.logo) {
      list.push(['info', 'With a logo, always test the code with your phone before you print it.']);
    }
    return list;
  }

  // ---------------------------------------------------------------- render

  function setButtons(enabled) {
    $('btn-png').disabled = !enabled;
    $('btn-svg').disabled = !enabled;
    $('btn-copy').disabled = !enabled;
  }

  function render() {
    var content = builders[chosen('type')]();
    var real = content.text !== '';
    var options = readStyle();
    options.text = real ? content.text : EXAMPLE;

    var tip = $('content-tip');
    tip.textContent = content.tip;
    tip.hidden = !content.tip;

    var box = $('preview-box');
    var model;
    try {
      model = QRRender.create(options);
    } catch (error) {
      current = null;
      box.className = 'preview is-error';
      $('preview-note').textContent = 'That is too much for one QR code. Please shorten your content.';
      $('meta').textContent = '';
      $('notices').innerHTML = '';
      $('inside').hidden = true;
      setButtons(false);
      updateJump(false);
      return;
    }

    current = { model: model, real: real };

    // The preview draws the logo as a separate, permanent <img> so a large
    // logo is not decoded again on every keystroke.
    var withoutLogo = Object.assign({}, model, { logo: null });
    $('preview').innerHTML = QRRender.toSvg(withoutLogo, { size: 400, id: 'qr-fill-preview' });
    $('jump-thumb').innerHTML = QRRender.toSvg(withoutLogo, { size: 54, id: 'qr-fill-thumb' });

    var overlay = $('preview-logo');
    if (model.logo) {
      var rect = model.logo.rect;
      overlay.style.left = (rect.x / model.total * 100) + '%';
      overlay.style.top = (rect.y / model.total * 100) + '%';
      overlay.style.width = (rect.w / model.total * 100) + '%';
      overlay.style.height = (rect.h / model.total * 100) + '%';
    }
    overlay.hidden = !model.logo;

    box.className = 'preview' + (real ? '' : ' is-example') + (model.background ? '' : ' is-transparent');
    $('preview-note').textContent = 'Your QR code will appear here';

    $('encoded').textContent = content.text;
    $('inside').hidden = !real;

    var px = QRRender.pixelSize(model, Number(val('size')));
    var cm = Math.max(2, Math.ceil(model.total * 0.045 * 2) / 2);
    $('meta').textContent = real ? px + ' × ' + px + ' px · print at least ' + cm + ' cm wide' : '';

    var problems = real ? findProblems(model) : [];
    var notices = $('notices');
    notices.innerHTML = '';
    for (var i = 0; i < problems.length; i++) {
      var item = document.createElement('li');
      item.className = 'notice ' + problems[i][0];
      item.textContent = problems[i][1];
      notices.appendChild(item);
    }

    setButtons(real);
    updateJump(real);
  }

  function updateJump(real) {
    $('jump-thumb').classList.toggle('is-example', !real);
    $('jump-state').textContent = real ? 'Ready to download' : 'Type your content to start';
    $('jump-link').textContent = real ? 'Download' : 'Preview';
  }

  function schedule() {
    clearTimeout(renderTimer);
    renderTimer = setTimeout(render, 60);
  }

  // -------------------------------------------------------------- download

  function say(message, bad) {
    var status = $('status');
    status.textContent = message;
    status.className = 'status' + (bad ? ' is-bad' : '');
    clearTimeout(statusTimer);
    statusTimer = setTimeout(function () {
      status.textContent = '';
    }, 6000);
  }

  function fileName() {
    var name = val('filename').trim()
      .replace(/\.(png|svg|jpe?g)$/i, '')
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_');
    return name || 'qr-code';
  }

  function save(blob, name) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 2000);
  }

  // Draws the current code on a canvas and hands back a PNG.
  function makePng(targetPx) {
    return new Promise(function (resolve, reject) {
      var canvas = document.createElement('canvas');
      var px = QRRender.toCanvas(current.model, canvas, targetPx, logo && logo.image);
      canvas.toBlob(function (blob) {
        if (blob) resolve({ blob: blob, px: px });
        else reject(new Error('Could not create the image.'));
      }, 'image/png');
    });
  }

  function downloadPng() {
    if (!current || !current.real) return;
    var name = fileName() + '.png';
    makePng(Number(val('size'))).then(function (result) {
      save(result.blob, name);
      say('Saved ' + name + ' (' + result.px + ' × ' + result.px + ' px)');
    }, function () {
      say('The image could not be created. Try a smaller image size.', true);
    });
  }

  function downloadSvg() {
    if (!current || !current.real) return;
    var name = fileName() + '.svg';
    var svg = '<?xml version="1.0" encoding="UTF-8"?>\n' +
      QRRender.toSvg(current.model, { size: 1000 });
    save(new Blob([svg], { type: 'image/svg+xml' }), name);
    say('Saved ' + name);
  }

  function copyPng() {
    if (!current || !current.real) return;
    function failed() {
      say('Copying is not available in this browser. Use Download instead.', true);
    }
    try {
      var png = makePng(1000).then(function (result) {
        return result.blob;
      });
      navigator.clipboard.write([new ClipboardItem({ 'image/png': png })]).then(function () {
        say('Copied. You can now paste it into a document or a chat.');
      }, failed);
    } catch (error) {
      failed();
    }
  }

  // ------------------------------------------------------------------ logo

  function logoProblem(message) {
    var el = $('logo-error');
    el.textContent = message;
    el.hidden = !message;
  }

  function showLogo() {
    $('logo-drop').hidden = !!logo;
    $('logo-loaded').hidden = !logo;
    if (logo) {
      $('logo-thumb').src = logo.src;
      $('preview-logo').src = logo.src;
      $('logo-name').textContent = logo.name;
    } else {
      $('logo-file').value = '';
      $('preview-logo').removeAttribute('src');
    }
    // a logo hides part of the code, so the strongest protection is forced
    $('ecc').disabled = !!logo;
    $('ecc-hint').textContent = logo
      ? 'Set to Highest automatically, because the logo covers part of the code.'
      : 'How much of the code can be scratched or covered and still scan.';
    schedule();
  }

  function loadLogo(file) {
    if (!file) return;
    logoProblem('');
    if (!/^image\//.test(file.type)) {
      logoProblem('That file is not an image. Choose a PNG, JPG or SVG.');
      return;
    }

    var unreadable = function () {
      logoProblem('That image could not be opened. Try a PNG or JPG.');
    };

    var reader = new FileReader();
    reader.onerror = unreadable;
    reader.onload = function () {
      var original = new Image();
      original.onerror = unreadable;
      original.onload = function () {
        // Redraw the logo at a sensible size: big photos would make the
        // SVG file huge, and tiny vector logos would come out blurry.
        var w = original.naturalWidth || 512;
        var h = original.naturalHeight || 512;
        var vector = file.type === 'image/svg+xml';
        var scale = 800 / Math.max(w, h);
        if (!vector) scale = Math.min(1, scale);

        var canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(w * scale));
        canvas.height = Math.max(1, Math.round(h * scale));
        canvas.getContext('2d').drawImage(original, 0, 0, canvas.width, canvas.height);

        var ready = new Image();
        ready.onerror = unreadable;
        ready.onload = function () {
          logo = {
            src: ready.src,
            width: canvas.width,
            height: canvas.height,
            image: ready,
            name: file.name
          };
          showLogo();
        };
        try {
          ready.src = canvas.toDataURL('image/png');
        } catch (error) {
          unreadable();
        }
      };
      original.src = reader.result;
    };
    reader.readAsDataURL(file);
  }

  // --------------------------------------------------------------- the form

  function showPanel() {
    var type = chosen('type');
    var panels = document.querySelectorAll('[data-panel]');
    for (var i = 0; i < panels.length; i++) {
      panels[i].hidden = panels[i].getAttribute('data-panel') !== type;
    }
  }

  function showFill() {
    var gradient = chosen('fill') === 'gradient';
    var extras = document.querySelectorAll('.gradient-only');
    for (var i = 0; i < extras.length; i++) extras[i].hidden = !gradient;
    $('color1-label').textContent = gradient ? 'First color' : 'Code color';
  }

  function syncForm() {
    showPanel();
    showFill();
    $('bg').disabled = $('bg-transparent').checked;
    $('wifi-pass').disabled = val('wifi-sec') === 'nopass';
    $('border-out').textContent = val('border');
  }

  function onChange(event) {
    if (event.target.id === 'logo-file') return;
    syncForm();
    schedule();
  }

  // The little pictures inside the Pattern and Corners buttons.
  function drawSamples() {
    function draw(el, sample) {
      el.innerHTML = '<svg viewBox="-0.5 -0.5 ' + (sample.size + 1) + ' ' + (sample.size + 1) +
        '" aria-hidden="true"><path fill="currentColor" fill-rule="evenodd" d="' +
        sample.path + '"/></svg>';
    }
    var i;
    var shapes = document.querySelectorAll('[data-shape]');
    for (i = 0; i < shapes.length; i++) {
      draw(shapes[i], QRRender.shapeSample(shapes[i].getAttribute('data-shape')));
    }
    var eyes = document.querySelectorAll('[data-eye]');
    for (i = 0; i < eyes.length; i++) {
      draw(eyes[i], QRRender.eyeSample(eyes[i].getAttribute('data-eye')));
    }
  }

  function start() {
    drawSamples();

    document.addEventListener('input', onChange);
    document.addEventListener('change', onChange);

    $('btn-png').addEventListener('click', downloadPng);
    $('btn-svg').addEventListener('click', downloadSvg);
    $('btn-copy').addEventListener('click', copyPng);
    if (!(navigator.clipboard && window.ClipboardItem)) $('btn-copy').hidden = true;

    $('swatches').addEventListener('click', function (event) {
      var color = event.target.getAttribute('data-color');
      if (!color) return;
      $('color1').value = color;
      schedule();
    });

    // logo: pick a file, or drop one on the box
    $('logo-file').addEventListener('change', function () {
      loadLogo(this.files[0]);
    });
    $('logo-remove').addEventListener('click', function () {
      logo = null;
      logoProblem('');
      showLogo();
    });
    var drop = $('logo-drop');
    drop.addEventListener('dragover', function () {
      drop.classList.add('is-over');
    });
    drop.addEventListener('dragleave', function () {
      drop.classList.remove('is-over');
    });
    drop.addEventListener('drop', function (event) {
      drop.classList.remove('is-over');
      if (event.dataTransfer && event.dataTransfer.files.length) {
        loadLogo(event.dataTransfer.files[0]);
      }
    });
    // a file dropped next to the box must not replace the page
    window.addEventListener('dragover', function (event) {
      event.preventDefault();
    });
    window.addEventListener('drop', function (event) {
      event.preventDefault();
    });

    // on small screens, show the shortcut bar while the preview is off screen
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        $('jump').hidden = entries[entries.length - 1].isIntersecting;
      }, { threshold: 0.12 }).observe($('result-card'));
    }

    syncForm();
    render();
  }

  start();
})();
