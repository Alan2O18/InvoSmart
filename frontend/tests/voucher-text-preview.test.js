import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildVoucherTextPreviewEntries,
  formatVoucherAmountCells,
  formatVoucherPaymentAmount,
  formatVoucherRocDate,
  pdfBaselineToCanvasTop,
  sanitizeVoucherText,
} from '../src/utils/voucher.js'

const sampleTextConfig = {
  font: { family: 'VoucherKaiU', url: '/api/voucher/fonts/kaiu.ttf' },
  fields: {
    voucherNo: { point: [78.5, 255], fontSize: 16, lineStep: 20, preview: { baselineRatio: 0.82 } },
    budgetItem: { point: [149, 270], fontSize: 18, maxChars: 3, preview: { baselineRatio: 0.82 } },
    amount: {
      xList: [188, 208, 228, 250.5, 271.5, 291, 312],
      y: 270,
      fontSize: 16,
      padLength: 7,
      padChar: '※',
      preview: { baselineRatio: 0.82 },
    },
    purpose: {
      rect: [333, 240, 462, 330],
      fontSize: 18,
      minFontSize: 12,
      lineHeight: 1.2,
      truncateAt: 80,
      truncateSuffix: '...(略)',
    },
    receiptCount: { point: [473.5, 92], fontSize: 16, preview: { baselineRatio: 0.82 } },
    payDate: { point: [205, 767], fontSize: 20, preview: { baselineRatio: 0.82 } },
    paymentAmount: { point: [314, 767], fontSize: 20, preview: { baselineRatio: 0.82 } },
  },
}

test('sanitizeVoucherText strips unsupported characters', () => {
  assert.equal(sanitizeVoucherText('茶水🎉#費'), '茶水費')
})

test('formatVoucherRocDate mirrors backend ROC output', () => {
  assert.equal(formatVoucherRocDate('2024-11-28'), '113/11/28')
  assert.equal(formatVoucherRocDate('invalid-date'), '')
})

test('formatVoucherAmountCells keeps current 7-cell policy', () => {
  assert.equal(formatVoucherAmountCells('146'), '※※※※146')
  assert.equal(formatVoucherAmountCells('abc'), '')
})

test('formatVoucherPaymentAmount formats bottom amount text', () => {
  assert.equal(formatVoucherPaymentAmount('4607'), '4,607元整')
  assert.equal(formatVoucherPaymentAmount('46.07'), '')
})

test('pdfBaselineToCanvasTop converts baseline to top origin', () => {
  assert.equal(pdfBaselineToCanvasTop(255, 16, 0.82), 241.88)
})

test('buildVoucherTextPreviewEntries builds text and textbox preview entries', () => {
  const entries = buildVoucherTextPreviewEntries({
    voucherNo: 'D-16-01\nD-16-02',
    budgetItem: '帶動組活動費',
    amount: '4607',
    purpose: '茶水、餐費',
    receiptCount: '3',
    payDate: '2024-11-28',
  }, sampleTextConfig)

  assert.ok(entries.find(entry => entry.key === 'voucherNo-0' && entry.text === 'D-16-01'))
  assert.ok(entries.find(entry => entry.key === 'voucherNo-1' && entry.text === 'D-16-02'))
  assert.ok(entries.find(entry => entry.key === 'budgetItem'))
  assert.ok(entries.find(entry => entry.key === 'purpose' && entry.type === 'textbox'))

  const amountEntries = entries.filter(entry => entry.key.startsWith('amount-'))
  assert.equal(amountEntries.length, 7)
  assert.equal(amountEntries[0].text, '※')
  assert.equal(amountEntries[6].text, '7')

  const payDateEntry = entries.find(entry => entry.key === 'payDate')
  assert.equal(payDateEntry.text, '113/11/28')
  assert.equal(payDateEntry.fontFamily, 'VoucherKaiU')

  const budgetEntry = entries.find(entry => entry.key === 'budgetItem')
  assert.equal(budgetEntry.text, '帶動組')

  const paymentAmountEntry = entries.find(entry => entry.key === 'paymentAmount')
  assert.equal(paymentAmountEntry.text, '4,607元整')
})