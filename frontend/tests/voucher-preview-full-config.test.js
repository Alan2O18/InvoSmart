import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { buildVoucherTextPreviewEntries } from '../src/utils/voucher.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const templateConfigPath = path.resolve(__dirname, '../../backend/data/voucher_template_config.json')

const rawTemplate = JSON.parse(fs.readFileSync(templateConfigPath, 'utf8'))
const textConfig = {
  font: { family: 'VoucherKaiU' },
  fields: rawTemplate.textFields || {},
}

const sampleFields = {
  voucherNo: 'D-16-01\nD-16-02\nD-16-03',
  budgetItem: '活動組專案',
  amount: '12345',
  purpose: '餐費、茶水、場地清潔與課程物資採購',
  receiptCount: '3',
  payDate: '2026-03-15',
}

const hasFinitePoint = (entry) => Number.isFinite(Number(entry.left)) && Number.isFinite(Number(entry.top))

test('full voucher template config renders all major preview fields', () => {
  const entries = buildVoucherTextPreviewEntries(sampleFields, textConfig)

  assert.ok(entries.length > 0, 'preview entries should not be empty')
  assert.ok(entries.some(e => e.key === 'budgetItem'), 'budgetItem should render')
  assert.ok(entries.some(e => e.key === 'receiptCount'), 'receiptCount should render')
  assert.ok(entries.some(e => e.key === 'payDate'), 'payDate should render')
  assert.ok(entries.some(e => e.key === 'paymentAmount'), 'paymentAmount should render')
  assert.ok(entries.some(e => e.key === 'purpose' && e.type === 'textbox'), 'purpose textbox should render')

  const voucherNoEntries = entries.filter(e => String(e.key).startsWith('voucherNo-'))
  assert.ok(voucherNoEntries.length >= 2, 'voucherNo multiline entries should render')

  const amountEntries = entries.filter(e => String(e.key).startsWith('amount-'))
  const expectedAmountCells = Array.isArray(textConfig.fields.amount?.xList)
    ? textConfig.fields.amount.xList.length
    : 0
  assert.equal(amountEntries.length, expectedAmountCells, 'amount cells count should match xList')

  for (const entry of entries) {
    assert.equal(hasFinitePoint(entry), true, `entry ${entry.key} should have finite coordinates`)
    assert.equal(typeof entry.text, 'string', `entry ${entry.key} should have text`)
    assert.equal(entry.text.length > 0, true, `entry ${entry.key} should not be empty`)
  }
})

test('payDate preview follows ROC format after ISO input conversion', () => {
  const entries = buildVoucherTextPreviewEntries({ payDate: '2026-03-15' }, textConfig)
  const payDate = entries.find(e => e.key === 'payDate')

  assert.ok(payDate, 'payDate entry should exist for ISO input')
  assert.equal(payDate.text, '115/03/15')
})
