/*
 * QR renderer for the Everyday Toolbox QR code generator.
 *
 * Turns text into a styled QR code, either as an SVG string or drawn on a
 * canvas. Both outputs are built from the same path, so the PNG and the SVG
 * always look identical.
 *
 * Nothing in this file touches the page, so it runs in the browser and in
 * Node.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./vendor/qrcode-generator.js'));
  } else {
    root.QRRender = factory(root.qrcode);
  }
})(typeof self !== 'undefined' ? self : this, function (qrcode) {
  'use strict';

  // Encode text as UTF-8 so accents, Arabic and emoji survive the trip.
  qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];

  var EYE = 7; // each corner "eye" (finder pattern) is 7 x 7 modules

  var SHAPES = ['square', 'rounded', 'dots', 'gapped', 'vbars', 'hbars'];
  var EYES = ['square', 'rounded', 'circle'];
  var FILLS = ['solid', 'horizontal', 'vertical', 'diagonal', 'radial'];

  // ---------------------------------------------------------------- helpers

  function num(v) {
    return String(Math.round(v * 1000) / 1000);
  }

  function clamp(v, min, max, fallback) {
    v = Number(v);
    if (!isFinite(v)) return fallback;
    return Math.min(max, Math.max(min, v));
  }

  function hex(color, fallback) {
    return /^#[0-9a-f]{6}$/i.test(color || '') ? color.toLowerCase() : fallback;
  }

  function pick(value, allowed) {
    return allowed.indexOf(value) >= 0 ? value : allowed[0];
  }

  // Rectangle with optional rounded corners, as an SVG path.
  // r is one radius, or [topLeft, topRight, bottomRight, bottomLeft].
  function rrect(x, y, w, h, r) {
    var tl, tr, br, bl;
    if (typeof r === 'number') {
      tl = tr = br = bl = r;
    } else {
      tl = r[0]; tr = r[1]; br = r[2]; bl = r[3];
    }
    var d = 'M' + num(x + tl) + ' ' + num(y) + 'H' + num(x + w - tr);
    if (tr) d += 'A' + num(tr) + ' ' + num(tr) + ' 0 0 1 ' + num(x + w) + ' ' + num(y + tr);
    d += 'V' + num(y + h - br);
    if (br) d += 'A' + num(br) + ' ' + num(br) + ' 0 0 1 ' + num(x + w - br) + ' ' + num(y + h);
    d += 'H' + num(x + bl);
    if (bl) d += 'A' + num(bl) + ' ' + num(bl) + ' 0 0 1 ' + num(x) + ' ' + num(y + h - bl);
    d += 'V' + num(y + tl);
    if (tl) d += 'A' + num(tl) + ' ' + num(tl) + ' 0 0 1 ' + num(x + tl) + ' ' + num(y);
    return d + 'Z';
  }

  function circle(cx, cy, r) {
    return 'M' + num(cx - r) + ' ' + num(cy) +
      'a' + num(r) + ' ' + num(r) + ' 0 1 0 ' + num(2 * r) + ' 0' +
      'a' + num(r) + ' ' + num(r) + ' 0 1 0 ' + num(-2 * r) + ' 0Z';
  }

  // ------------------------------------------------------------ the shapes
  //
  // The sizes below (dot radius, gaps, corner radius) were chosen by scan
  // tests: each shape was blurred, tilted and shrunk the way a phone photo
  // would be, then read back with five different decoders. Bigger gaps or
  // rounder eyes look bolder but scan worse.

  // Traces the outline of every group of touching modules, so neighbours
  // become one clean shape. Drawing each module on its own would leave
  // hairline gaps between them at some zoom levels and in print.
  // radius > 0 rounds the outward corners.
  function outlines(n, on, off, radius) {
    var w = n + 1;                // grid points per row
    var DX = [1, 0, -1, 0];       // directions: east, south, west, north
    var DY = [0, 1, 0, -1];
    var edges = {};               // (grid point * 4 + direction) -> not walked yet?
    var r, c;

    // every module side that faces an empty neighbour is part of an outline;
    // sides are stored clockwise, so the filled area is always on the right
    for (r = 0; r < n; r++) {
      for (c = 0; c < n; c++) {
        if (!on(r, c)) continue;
        if (!on(r - 1, c)) edges[(r * w + c) * 4] = true;
        if (!on(r, c + 1)) edges[(r * w + c + 1) * 4 + 1] = true;
        if (!on(r + 1, c)) edges[((r + 1) * w + c + 1) * 4 + 2] = true;
        if (!on(r, c - 1)) edges[((r + 1) * w + c) * 4 + 3] = true;
      }
    }

    var d = '';
    for (var key in edges) {
      if (!edges[key]) continue;

      // walk around one outline, noting each corner
      var first = Number(key);
      var x = (first >> 2) % w;
      var y = Math.floor((first >> 2) / w);
      var dir = first & 3;
      var corners = [];
      do {
        edges[(y * w + x) * 4 + dir] = false;
        x += DX[dir];
        y += DY[dir];
        var here = (y * w + x) * 4;
        var right = (dir + 1) % 4;
        // where two modules touch only by a corner, turning right keeps
        // them as two separate shapes
        var next = (here + right) in edges ? right
          : (here + dir) in edges ? dir
            : (dir + 3) % 4;
        if (next !== dir) {
          var rounded = next === right ? radius : 0;
          corners.push({
            horizontal: dir % 2 === 0,
            inX: x - DX[dir] * rounded, inY: y - DY[dir] * rounded,
            outX: x + DX[next] * rounded, outY: y + DY[next] * rounded,
            radius: rounded
          });
        }
        dir = next;
      } while ((y * w + x) * 4 + dir !== first);

      var last = corners[corners.length - 1];
      var px = last.outX;
      var py = last.outY;
      d += 'M' + num(off + px) + ' ' + num(off + py);
      for (var i = 0; i < corners.length; i++) {
        var corner = corners[i];
        if (corner.inX !== px || corner.inY !== py) {
          d += corner.horizontal ? 'H' + num(off + corner.inX) : 'V' + num(off + corner.inY);
        }
        if (corner.radius) {
          d += 'A' + num(corner.radius) + ' ' + num(corner.radius) + ' 0 0 1 ' +
            num(off + corner.outX) + ' ' + num(off + corner.outY);
        }
        px = corner.outX;
        py = corner.outY;
      }
      d += 'Z';
    }
    return d;
  }

  // Joins the modules of each row (or column) into bars with round ends.
  function runs(n, on, off, vertical, thickness, radius) {
    var d = '';
    var inset = (1 - thickness) / 2;
    for (var i = 0; i < n; i++) {
      var start = -1;
      for (var j = 0; j <= n; j++) {
        var lit = j < n && (vertical ? on(j, i) : on(i, j));
        if (lit && start < 0) start = j;
        if (!lit && start >= 0) {
          d += vertical
            ? rrect(off + i + inset, off + start, thickness, j - start, radius)
            : rrect(off + start, off + i + inset, j - start, thickness, radius);
          start = -1;
        }
      }
    }
    return d;
  }

  function modulesPath(n, on, shape, off) {
    if (shape === 'square') return outlines(n, on, off, 0);
    if (shape === 'rounded') return outlines(n, on, off, 0.5);
    if (shape === 'vbars') return runs(n, on, off, true, 0.9, 0.45);
    if (shape === 'hbars') return runs(n, on, off, false, 0.9, 0.45);

    var d = '';
    for (var r = 0; r < n; r++) {
      for (var c = 0; c < n; c++) {
        if (!on(r, c)) continue;
        d += shape === 'dots'
          ? circle(off + c + 0.5, off + r + 0.5, 0.5)
          : rrect(off + c + 0.07, off + r + 0.07, 0.86, 0.86, 0);   // gapped
      }
    }
    return d;
  }

  // One eye: outer ring + hole + centre (the path is filled "evenodd").
  function eyePath(x, y, style) {
    if (style === 'circle') {
      return circle(x + 3.5, y + 3.5, 3.5) + circle(x + 3.5, y + 3.5, 2.5) +
        circle(x + 3.5, y + 3.5, 1.5);
    }
    if (style === 'rounded') {
      // gently rounded: strict scanners locate the code by the eye's corners
      return rrect(x, y, 7, 7, 0.75) + rrect(x + 1, y + 1, 5, 5, 0) +
        rrect(x + 2, y + 2, 3, 3, 0.4);
    }
    return rrect(x, y, 7, 7, 0) + rrect(x + 1, y + 1, 5, 5, 0) +
      rrect(x + 2, y + 2, 3, 3, 0);
  }

  // ------------------------------------------------------------- the model

  function encode(text, ecc) {
    var qr = qrcode(0, ecc); // 0 = the smallest size that fits the text
    qr.addData(text);
    try {
      qr.make();
    } catch (e) {
      var error = new Error('The content is too long for a QR code.');
      error.code = 'TOO_LONG';
      throw error;
    }
    return qr;
  }

  /*
   * create(options) -> model
   *
   *   text        what the code contains (required)
   *   ecc         'L' | 'M' | 'Q' | 'H'   error correction (default 'Q')
   *   border      quiet zone in modules   (default 4)
   *   shape       one of SHAPES           (default 'square')
   *   eye         one of EYES             (default 'square')
   *   fill        { type: one of FILLS, color1, color2 }
   *   background  '#rrggbb', or null for transparent
   *   logo        { src, width, height, size } - size is the share of the
   *               code's width the logo covers (0.14 to 0.3)
   */
  function create(options) {
    var text = String(options.text == null ? '' : options.text);
    var logo = options.logo && options.logo.src ? options.logo : null;

    // A logo hides part of the code, so it gets the strongest error
    // correction. Scan tests showed that is enough even for the tiniest codes.
    var ecc = logo ? 'H' : pick(options.ecc, ['Q', 'L', 'M', 'H']);
    var qr = encode(text, ecc);

    var n = qr.getModuleCount();
    var border = Math.round(clamp(options.border, 0, 20, 4));
    var total = n + 2 * border;
    var shape = pick(options.shape, SHAPES);
    var eye = pick(options.eye, EYES);

    var cut = null;
    var logoRect = null;
    if (logo) {
      var share = clamp(logo.size, 0.14, 0.3, 0.22);
      // odd number of modules, so the cut-out is centred on whole modules
      var side = Math.max(3, 2 * Math.round((n * share - 1) / 2) + 1);
      var start = (n - side) / 2;
      cut = { from: start, to: start + side };

      var room = side - 1; // half a module of breathing space on each side
      var ratio = (logo.width || 1) / (logo.height || 1);
      var w = ratio >= 1 ? room : room * ratio;
      var h = ratio >= 1 ? room / ratio : room;
      logoRect = {
        x: border + start + (side - w) / 2,
        y: border + start + (side - h) / 2,
        w: w,
        h: h
      };
    }

    function inEye(r, c) {
      return (r < EYE && c < EYE) ||
        (r < EYE && c >= n - EYE) ||
        (r >= n - EYE && c < EYE);
    }

    function on(r, c) {
      if (r < 0 || c < 0 || r >= n || c >= n) return false;
      if (inEye(r, c)) return false;
      if (cut && r >= cut.from && r < cut.to && c >= cut.from && c < cut.to) return false;
      return qr.isDark(r, c);
    }

    var path = modulesPath(n, on, shape, border) +
      eyePath(border, border, eye) +
      eyePath(border + n - EYE, border, eye) +
      eyePath(border, border + n - EYE, eye);

    var fill = options.fill || {};
    return {
      text: text,
      modules: n,
      version: (n - 17) / 4,
      ecc: ecc,
      border: border,
      total: total,
      shape: shape,
      eye: eye,
      path: path,
      fill: {
        type: pick(fill.type, FILLS),
        color1: hex(fill.color1, '#000000'),
        color2: hex(fill.color2, '#1f4e79')
      },
      background: options.background === null ? null : hex(options.background, '#ffffff'),
      logo: logo ? { src: logo.src, rect: logoRect } : null
    };
  }

  // Where the gradient starts and ends, in module units.
  function gradientGeometry(model) {
    var a = model.border;
    var z = model.border + model.modules;
    var mid = model.total / 2;
    switch (model.fill.type) {
      case 'horizontal': return { x1: a, y1: mid, x2: z, y2: mid };
      case 'vertical': return { x1: mid, y1: a, x2: mid, y2: z };
      case 'diagonal': return { x1: a, y1: a, x2: z, y2: z };
      case 'radial': return { cx: mid, cy: mid, r: model.modules * 0.7 };
      default: return null;
    }
  }

  // ------------------------------------------------------------------- SVG

  /*
   * toSvg(model, { size, id }) -> string
   *   size  width/height written in the file, in pixels (default 1000)
   *   id    id used for the gradient (change it when several codes share a page)
   */
  function toSvg(model, options) {
    options = options || {};
    var size = Math.round(clamp(options.size, 16, 20000, 1000));
    var id = /^[\w-]+$/.test(options.id || '') ? options.id : 'qr-fill';
    var t = num(model.total);
    var g = gradientGeometry(model);
    var paint = model.fill.color1;
    var defs = '';

    if (g) {
      var stops = '<stop offset="0" stop-color="' + model.fill.color1 + '"/>' +
        '<stop offset="1" stop-color="' + model.fill.color2 + '"/>';
      defs = model.fill.type === 'radial'
        ? '<defs><radialGradient id="' + id + '" gradientUnits="userSpaceOnUse" cx="' +
          num(g.cx) + '" cy="' + num(g.cy) + '" r="' + num(g.r) + '">' + stops +
          '</radialGradient></defs>'
        : '<defs><linearGradient id="' + id + '" gradientUnits="userSpaceOnUse" x1="' +
          num(g.x1) + '" y1="' + num(g.y1) + '" x2="' + num(g.x2) + '" y2="' + num(g.y2) +
          '">' + stops + '</linearGradient></defs>';
      paint = 'url(#' + id + ')';
    }

    var svg = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"' +
      ' viewBox="0 0 ' + t + ' ' + t + '" width="' + size + '" height="' + size + '"' +
      ' role="img" aria-label="QR code">' + defs;

    if (model.background) {
      svg += '<rect width="' + t + '" height="' + t + '" fill="' + model.background + '"/>';
    }
    svg += '<path fill="' + paint + '" fill-rule="evenodd" d="' + model.path + '"/>';

    if (model.logo) {
      var r = model.logo.rect;
      svg += '<image x="' + num(r.x) + '" y="' + num(r.y) + '" width="' + num(r.w) +
        '" height="' + num(r.h) + '" preserveAspectRatio="xMidYMid meet" xlink:href="' +
        String(model.logo.src).replace(/[<>"&]/g, '') + '"/>';
    }
    return svg + '</svg>';
  }

  // ---------------------------------------------------------------- canvas

  // Every module gets the same whole number of pixels, so edges stay sharp.
  // The result is the largest such size that fits in targetPx.
  function pixelSize(model, targetPx) {
    var box = Math.max(1, Math.floor(clamp(targetPx, 1, 20000, 1000) / model.total));
    return box * model.total;
  }

  /*
   * toCanvas(model, canvas, targetPx, logoImage) -> final size in pixels
   *   logoImage  a loaded <img> for model.logo (ignored when there is no logo)
   */
  function toCanvas(model, canvas, targetPx, logoImage) {
    var px = pixelSize(model, targetPx);
    var box = px / model.total;
    canvas.width = px;
    canvas.height = px;

    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, px, px);
    if (model.background) {
      ctx.fillStyle = model.background;
      ctx.fillRect(0, 0, px, px);
    }

    ctx.save();
    ctx.scale(box, box);

    var g = gradientGeometry(model);
    var paint = model.fill.color1;
    if (g) {
      paint = model.fill.type === 'radial'
        ? ctx.createRadialGradient(g.cx, g.cy, 0, g.cx, g.cy, g.r)
        : ctx.createLinearGradient(g.x1, g.y1, g.x2, g.y2);
      paint.addColorStop(0, model.fill.color1);
      paint.addColorStop(1, model.fill.color2);
    }
    ctx.fillStyle = paint;
    ctx.fill(new Path2D(model.path), 'evenodd');

    if (model.logo && logoImage) {
      var r = model.logo.rect;
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(logoImage, r.x, r.y, r.w, r.h);
    }
    ctx.restore();
    return px;
  }

  // ------------------------------------------- small samples for the pickers

  var SAMPLE = [
    '1101011',
    '1001101',
    '0110100',
    '1101110',
    '0010011',
    '1011010',
    '1100111'
  ];

  // A little 7 x 7 pattern drawn with the given module shape.
  function shapeSample(shape) {
    function on(r, c) {
      return r >= 0 && c >= 0 && r < 7 && c < 7 && SAMPLE[r].charAt(c) === '1';
    }
    return { size: 7, path: modulesPath(7, on, pick(shape, SHAPES), 0) };
  }

  // A single eye drawn in the given style.
  function eyeSample(style) {
    return { size: 7, path: eyePath(0, 0, pick(style, EYES)) };
  }

  return {
    SHAPES: SHAPES,
    EYES: EYES,
    FILLS: FILLS,
    create: create,
    toSvg: toSvg,
    toCanvas: toCanvas,
    pixelSize: pixelSize,
    shapeSample: shapeSample,
    eyeSample: eyeSample
  };
});
