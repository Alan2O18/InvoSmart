export function collectUsedJobIds(pages = []) {
  const used = new Set()
  pages.forEach(page => {
    ;(page.images || []).forEach(image => {
      if (image?.jobId) used.add(image.jobId)
    })
  })
  return used
}

export function parseDateString(value) {
  if (value === null || value === undefined) return NaN
  const raw = String(value).trim()
  if (!raw) return NaN

  let y = 0
  let m = 0
  let d = 0

  if (/^\d{8}$/.test(raw)) {
    y = Number(raw.slice(0, 4))
    m = Number(raw.slice(4, 6))
    d = Number(raw.slice(6, 8))
  } else {
    const matched = raw.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/)
    if (!matched) return NaN
    y = Number(matched[1])
    m = Number(matched[2])
    d = Number(matched[3])
  }

  if (m < 1 || m > 12 || d < 1 || d > 31) return NaN

  const dt = new Date(Date.UTC(y, m - 1, d))
  if (
    dt.getUTCFullYear() !== y ||
    dt.getUTCMonth() + 1 !== m ||
    dt.getUTCDate() !== d
  ) {
    return NaN
  }

  return dt.getTime()
}

export function normalizeDateToISO(value) {
  const ts = parseDateString(value)
  if (Number.isNaN(ts)) return ''
  const dt = new Date(ts)
  const yyyy = dt.getUTCFullYear()
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(dt.getUTCDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export function hasInvalidDate(pages = []) {
  return pages.some(page => {
    const payDate = page?.fields?.payDate
    const hasImages = (page.images || []).length > 0
    // Empty date on a page with images is invalid (Defense #10/#11)
    if (!payDate && hasImages) return true
    if (!payDate) return false
    return Number.isNaN(parseDateString(payDate))
  })
}

export function hasDecimalAmount(pages = []) {
  return pages.some(page => {
    const amount = page?.fields?.amount
    if (!amount) return false
    return /\./.test(String(amount))
  })
}

export function hasExcessiveAmount(pages = []) {
  return pages.some(page => {
    const amount = page?.fields?.amount
    if (!amount) return false
    const num = parseInt(String(amount), 10)
    return !Number.isNaN(num) && num > 9999999
  })
}

export function canGenerateVoucher(pages = [], isSaving = false) {
  if (isSaving) return false
  if (hasInvalidDate(pages)) return false
  if (hasDecimalAmount(pages)) return false
  if (hasExcessiveAmount(pages)) return false
  return pages.some(page => (page.images || []).length > 0)
}

export function round2(value) {
  return Math.round(Number(value) * 100) / 100
}

export function clampImageRect(rect, safeZone = { x0: 30, y0: 394, x1: 565, y1: 730 }) {
  const width = Math.max(1, Number(rect.w || 0))
  const height = Math.max(1, Number(rect.h || 0))
  const maxX = safeZone.x1 - width
  const maxY = safeZone.y1 - height

  const x = Math.min(Math.max(Number(rect.x || 0), safeZone.x0), maxX)
  const y = Math.min(Math.max(Number(rect.y || 0), safeZone.y0), maxY)

  return {
    ...rect,
    x: round2(x),
    y: round2(y),
    w: round2(width),
    h: round2(height),
  }
}

/**
 * AABB collision — do two rectangles overlap?
 * @param {{ x: number, y: number, w: number, h: number }} a
 * @param {{ x: number, y: number, w: number, h: number }} b
 * @returns {boolean}
 */
export function rectsOverlap(a, b) {
  return !(
    a.x + a.w <= b.x ||
    b.x + b.w <= a.x ||
    a.y + a.h <= b.y ||
    b.y + b.h <= a.y
  )
}

/**
 * Given a list of image rects, return the Set of jobIds that have overlaps.
 * @param {Array<{ jobId: string, x: number, y: number, w: number, h: number }>} images
 * @returns {Set<string>}
 */
export function findOverlappingJobIds(images = []) {
  const overlapping = new Set()
  for (let i = 0; i < images.length; i++) {
    for (let j = i + 1; j < images.length; j++) {
      if (rectsOverlap(images[i], images[j])) {
        overlapping.add(images[i].jobId)
        overlapping.add(images[j].jobId)
      }
    }
  }
  return overlapping
}

/**
 * O(N log H) auto-layout — binary search for max uniform height H.
 * @param {Array<{ jobId: string, originalWidth: number, originalHeight: number }>} images
 * @param {{ x0: number, y0: number, x1: number, y1: number }} safeZone
 * @returns {Array<{ jobId: string, x: number, y: number, w: number, h: number }>|null}
 */
export function autoLayoutImages(images, safeZone = { x0: 30, y0: 394, x1: 565, y1: 730 }) {
  if (!images.length) return null
  const maxWidth = safeZone.x1 - safeZone.x0
  const maxHeight = safeZone.y1 - safeZone.y0
  const GAP = 4

  function simulateLayout(items, H) {
    let rows = 1
    let currentRowWidth = 0
    for (const item of items) {
      const scaledW = (item.originalWidth / item.originalHeight) * H
      if (scaledW > maxWidth) return Number.POSITIVE_INFINITY
      if (currentRowWidth > 0 && currentRowWidth + GAP + scaledW > maxWidth) {
        rows++
        currentRowWidth = scaledW
      } else {
        currentRowWidth += (currentRowWidth > 0 ? GAP : 0) + scaledW
      }
    }
    return rows
  }

  let lo = 20, hi = maxHeight
  for (let i = 0; i < 50; i++) {
    const mid = (lo + hi) / 2
    const rows = simulateLayout(images, mid)
    if (rows * mid + (rows - 1) * GAP <= maxHeight) {
      lo = mid
    } else {
      hi = mid
    }
  }

  const H = Math.floor(lo)
  if (H < 20) return null

  const result = []
  let curX = safeZone.x0
  let curY = safeZone.y0

  for (const item of images) {
    const scaledW = round2((item.originalWidth / item.originalHeight) * H)
    if (scaledW > maxWidth) return null
    if (curX > safeZone.x0 && curX + scaledW > safeZone.x0 + maxWidth) {
      curX = safeZone.x0
      curY += H + GAP
    }
    result.push({
      jobId: item.jobId,
      x: round2(curX),
      y: round2(curY),
      w: scaledW,
      h: H,
    })
    curX += scaledW + GAP
  }

  // Final validation: ensure last row bottom edge fits within safe zone
  const lastBottom = result.length ? result[result.length - 1].y + H : 0
  if (lastBottom > safeZone.y1) return null

  return result
}
