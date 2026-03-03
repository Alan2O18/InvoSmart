export function collectUsedJobIds(pages = []) {
  const used = new Set()
  pages.forEach(page => {
    ;(page.images || []).forEach(image => {
      if (image?.jobId) used.add(image.jobId)
    })
  })
  return used
}

export function hasInvalidDate(pages = []) {
  return pages.some(page => {
    const payDate = page?.fields?.payDate
    const hasImages = (page.images || []).length > 0
    // Empty date on a page with images is invalid (Defense #10/#11)
    if (!payDate && hasImages) return true
    if (!payDate) return false
    return Number.isNaN(Date.parse(payDate))
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
