import test from 'node:test'
import assert from 'node:assert/strict'

import {
  canGenerateVoucher,
  clampImageRect,
  collectUsedJobIds,
  hasDecimalAmount,
  hasExcessiveAmount,
  hasInvalidDate,
  round2,
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

test('hasExcessiveAmount detects amount > 9999999 (Defense #15)', () => {
  assert.equal(hasExcessiveAmount([{ fields: { amount: '9999999' } }]), false)
  assert.equal(hasExcessiveAmount([{ fields: { amount: '10000000' } }]), true)
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
      [{ fields: { amount: '10000000', payDate: '2024-11-28' }, images: [{ jobId: 'a' }] }],
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
