import test from 'node:test'
import assert from 'node:assert/strict'

import {
  canGenerateVoucher,
  clampImageRect,
  collectUsedJobIds,
  hasDecimalAmount,
  hasExcessiveAmount,
  hasInvalidDate,
  normalizeDateToISO,
  parseDateString,
  round2,
  rectsOverlap,
  findOverlappingJobIds,
  autoLayoutImages,
} from '../src/utils/voucher.js'

test('collectUsedJobIds aggregates all pages', () => {
  const used = collectUsedJobIds([
    { images: [{ jobId: 'a' }, { jobId: 'b' }] },
    { images: [{ jobId: 'b' }, { jobId: 'c' }] },
  ])

  assert.equal(used.has('a'), true)
  assert.equal(used.has('b'), true)
  assert.equal(used.has('c'), true)
  assert.equal(used.size, 3)
})

test('hasInvalidDate detects invalid payDate format', () => {
  assert.equal(hasInvalidDate([{ fields: { payDate: '2024-11-28' } }]), false)
  assert.equal(hasInvalidDate([{ fields: { payDate: '2024/99/01' } }]), true)
})

test('parseDateString supports YYYYMMDD and slash date formats', () => {
  assert.equal(Number.isNaN(parseDateString('20240301')), false)
  assert.equal(Number.isNaN(parseDateString('2024/03/01')), false)
  assert.equal(Number.isNaN(parseDateString('2024-03-01')), false)
})

test('parseDateString rejects invalid calendar dates strictly', () => {
  assert.equal(Number.isNaN(parseDateString('2024-02-31')), true)
  assert.equal(Number.isNaN(parseDateString('20240231')), true)
  assert.equal(Number.isNaN(parseDateString('2024/13/01')), true)
})

test('normalizeDateToISO returns normalized ISO date only for valid input', () => {
  assert.equal(normalizeDateToISO('20240301'), '2024-03-01')
  assert.equal(normalizeDateToISO('2024/3/1'), '2024-03-01')
  assert.equal(normalizeDateToISO('2024-02-31'), '')
})

test('hasInvalidDate flags empty date on page with images (Defense #10/#11)', () => {
  // Empty date + images → invalid
  assert.equal(
    hasInvalidDate([{ fields: { payDate: '' }, images: [{ jobId: 'j1' }] }]),
    true,
  )
  // Empty date + no images → ok (draft scenario)
  assert.equal(
    hasInvalidDate([{ fields: { payDate: '' }, images: [] }]),
    false,
  )
  // Missing payDate + images → invalid
  assert.equal(
    hasInvalidDate([{ fields: {}, images: [{ jobId: 'j1' }] }]),
    true,
  )
})

test('hasDecimalAmount detects decimal amount', () => {
  assert.equal(hasDecimalAmount([{ fields: { amount: '4607' } }]), false)
  assert.equal(hasDecimalAmount([{ fields: { amount: '4607.5' } }]), true)
})

test('hasExcessiveAmount detects amount > 999999 (six-cell policy)', () => {
  assert.equal(hasExcessiveAmount([{ fields: { amount: '999999' } }]), false)
  assert.equal(hasExcessiveAmount([{ fields: { amount: '1000000' } }]), true)
  assert.equal(hasExcessiveAmount([{ fields: { amount: '' } }]), false)
  assert.equal(hasExcessiveAmount([{ fields: { amount: '0' } }]), false)
})

test('canGenerateVoucher honors lock conditions', () => {
  const pages = [
    {
      fields: { amount: '100', payDate: '2024-11-28' },
      images: [{ jobId: 'a' }],
    },
  ]

  assert.equal(canGenerateVoucher(pages, false), true)
  assert.equal(canGenerateVoucher(pages, true), false)
  assert.equal(
    canGenerateVoucher(
      [{ fields: { amount: '100.5', payDate: '2024-11-28' }, images: [{ jobId: 'a' }] }],
      false,
    ),
    false,
  )
  assert.equal(
    canGenerateVoucher(
      [{ fields: { amount: '100', payDate: 'invalid-date' }, images: [{ jobId: 'a' }] }],
      false,
    ),
    false,
  )
  // Excessive amount blocks generation
  assert.equal(
    canGenerateVoucher(
      [{ fields: { amount: '1000000', payDate: '2024-11-28' }, images: [{ jobId: 'a' }] }],
      false,
    ),
    false,
  )
  // Empty payDate with images blocks generation
  assert.equal(
    canGenerateVoucher(
      [{ fields: { amount: '100', payDate: '' }, images: [{ jobId: 'a' }] }],
      false,
    ),
    false,
  )
})

test('round2 keeps 2-digit precision', () => {
  assert.equal(round2(1.236), 1.24)
  assert.equal(round2(1.234), 1.23)
})

test('clampImageRect keeps image inside safe zone', () => {
  const rect = clampImageRect({ x: 0, y: 0, w: 200, h: 150 })
  assert.equal(rect.x, 30)
  assert.equal(rect.y, 394)

  const rect2 = clampImageRect({ x: 999, y: 999, w: 200, h: 150 })
  assert.equal(rect2.x, 365)
  assert.equal(rect2.y, 580)
})

// ── rectsOverlap tests ──────────────────────────────────────────────────────
test('rectsOverlap returns true for overlapping rectangles', () => {
  const a = { x: 0, y: 0, w: 100, h: 100 }
  const b = { x: 50, y: 50, w: 100, h: 100 }
  assert.equal(rectsOverlap(a, b), true)
})

test('rectsOverlap returns false for edge-touching rectangles', () => {
  const a = { x: 0, y: 0, w: 100, h: 100 }
  const b = { x: 100, y: 0, w: 100, h: 100 }
  assert.equal(rectsOverlap(a, b), false)
})

test('rectsOverlap returns false for separated rectangles', () => {
  const a = { x: 0, y: 0, w: 50, h: 50 }
  const b = { x: 200, y: 200, w: 50, h: 50 }
  assert.equal(rectsOverlap(a, b), false)
})

// ── findOverlappingJobIds tests ─────────────────────────────────────────────
test('findOverlappingJobIds detects partial overlap', () => {
  const images = [
    { jobId: 'a', x: 0, y: 0, w: 100, h: 100 },
    { jobId: 'b', x: 50, y: 50, w: 100, h: 100 },
  ]
  const overlapping = findOverlappingJobIds(images)
  assert.equal(overlapping.has('a'), true)
  assert.equal(overlapping.has('b'), true)
})

test('findOverlappingJobIds multi-overlap marks all involved', () => {
  const images = [
    { jobId: 'a', x: 0, y: 0, w: 100, h: 100 },
    { jobId: 'b', x: 50, y: 0, w: 100, h: 100 },
    { jobId: 'c', x: 300, y: 0, w: 50, h: 50 },
  ]
  const overlapping = findOverlappingJobIds(images)
  assert.equal(overlapping.has('a'), true)
  assert.equal(overlapping.has('b'), true)
  assert.equal(overlapping.has('c'), false)
  assert.equal(overlapping.size, 2)
})

test('findOverlappingJobIds returns empty set when no overlap', () => {
  const images = [
    { jobId: 'a', x: 0, y: 0, w: 50, h: 50 },
    { jobId: 'b', x: 100, y: 0, w: 50, h: 50 },
  ]
  const overlapping = findOverlappingJobIds(images)
  assert.equal(overlapping.size, 0)
})

// ── autoLayoutImages tests ──────────────────────────────────────────────────
test('autoLayoutImages single image fills zone height', () => {
  const items = [{ jobId: 'a', originalWidth: 200, originalHeight: 100 }]
  const result = autoLayoutImages(items)
  assert.ok(result)
  assert.equal(result.length, 1)
  assert.equal(result[0].jobId, 'a')
  assert.ok(result[0].h > 0)
  assert.ok(result[0].w > 0)
  assert.ok(result[0].x >= 30)
  assert.ok(result[0].y >= 394)
})

test('autoLayoutImages multiple images fit within safe zone', () => {
  const items = [
    { jobId: 'a', originalWidth: 200, originalHeight: 100 },
    { jobId: 'b', originalWidth: 150, originalHeight: 100 },
    { jobId: 'c', originalWidth: 180, originalHeight: 100 },
  ]
  const safeZone = { x0: 30, y0: 394, x1: 565, y1: 730 }
  const result = autoLayoutImages(items, safeZone)
  assert.ok(result)
  assert.equal(result.length, 3)
  // All within safe zone (allow +2 tolerance for floor rounding)
  for (const r of result) {
    assert.ok(r.x >= safeZone.x0, `x ${r.x} >= ${safeZone.x0}`)
    assert.ok(r.y >= safeZone.y0, `y ${r.y} >= ${safeZone.y0}`)
    assert.ok(r.x + r.w <= safeZone.x1 + 2, `right edge within zone`)
    assert.ok(r.y + r.h <= safeZone.y1 + 2, `bottom edge within zone`)
  }
})

test('autoLayoutImages returns null for empty input', () => {
  assert.equal(autoLayoutImages([]), null)
})

test('autoLayoutImages returns null when images cannot fit (overflow)', () => {
  // Tiny safe zone, huge images
  const items = Array.from({ length: 50 }, (_, i) => ({
    jobId: `img${i}`,
    originalWidth: 1000,
    originalHeight: 1000,
  }))
  const tinyZone = { x0: 0, y0: 0, x1: 30, y1: 30 }
  const result = autoLayoutImages(items, tinyZone)
  assert.equal(result, null)
})

test('autoLayoutImages returns null when single image is too wide for safe zone', () => {
  const items = [
    { jobId: 'wide', originalWidth: 5000, originalHeight: 100 },
  ]
  const zone = { x0: 0, y0: 0, x1: 120, y1: 300 }
  const result = autoLayoutImages(items, zone)
  assert.equal(result, null)
})
