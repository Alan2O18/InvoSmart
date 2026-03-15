import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { buildVoucherTextPreviewEntries } from '../src/utils/voucher.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const vuePath = path.resolve(__dirname, '../src/views/VoucherTemplateConfigView.vue')
const templateConfigPath = path.resolve(__dirname, '../../backend/data/voucher_template_config.json')

const vueSource = fs.readFileSync(vuePath, 'utf8')
const rawTemplate = JSON.parse(fs.readFileSync(templateConfigPath, 'utf8'))

const textConfig = {
  font: { family: 'VoucherKaiU' },
  fields: rawTemplate.textFields || {},
}

const isFiniteEntry = (entry) => Number.isFinite(Number(entry.left)) && Number.isFinite(Number(entry.top))

const findByPrefix = (entries, prefix) => entries.filter(entry => String(entry.key).startsWith(prefix))

test('template config view keeps preview builder contract wiring', () => {
  assert.equal(
    vueSource.includes('buildVoucherTextPreviewEntries'),
    true,
    'Config view must keep using shared buildVoucherTextPreviewEntries.',
  )

  assert.match(
    vueSource,
    /payDate:\s*'\d{4}-\d{2}-\d{2}'/,
    'payDate sample must stay ISO format so preview formatter can output ROC date.',
  )

  assert.equal(
    vueSource.includes("amount: FIELD_SAMPLES.paymentAmount.replace(/,/g, '')"),
    true,
    'Config preview sample should derive amount digits from paymentAmount sample to avoid drift.',
  )
})

test('critical field matrix renders expected preview outputs', () => {
  const entries = buildVoucherTextPreviewEntries({
    voucherNo: 'D-16-01\nD-16-02\nD-16-03',
    budgetItem: '活動組專案測試',
    amount: '12345',
    purpose: '餐費、茶水、場地清潔與課程物資採購',
    receiptCount: '7',
    payDate: '2026-03-15',
  }, textConfig)

  const voucherNoEntries = findByPrefix(entries, 'voucherNo-')
  const amountEntries = findByPrefix(entries, 'amount-')

  assert.ok(voucherNoEntries.length >= 3, 'voucherNo multiline must render')
  assert.equal(entries.some(entry => entry.key === 'budgetItem'), true, 'budgetItem must render')
  assert.equal(entries.some(entry => entry.key === 'receiptCount'), true, 'receiptCount must render')
  assert.equal(entries.some(entry => entry.key === 'payDate'), true, 'payDate must render')
  assert.equal(entries.some(entry => entry.key === 'paymentAmount'), true, 'paymentAmount must render')
  assert.equal(entries.some(entry => entry.key === 'purpose' && entry.type === 'textbox'), true, 'purpose textbox must render')

  const expectedAmountCells = Array.isArray(textConfig.fields.amount?.xList)
    ? textConfig.fields.amount.xList.length
    : 0
  assert.equal(amountEntries.length, expectedAmountCells, 'amount cells count must match template xList')

  const payDate = entries.find(entry => entry.key === 'payDate')
  const paymentAmount = entries.find(entry => entry.key === 'paymentAmount')
  const budgetItem = entries.find(entry => entry.key === 'budgetItem')

  assert.equal(payDate.text, '115/03/15')
  assert.equal(paymentAmount.text, '12,345元整')
  assert.equal(budgetItem.text.length <= Number(textConfig.fields.budgetItem?.maxChars || 999), true)

  for (const entry of entries) {
    assert.equal(isFiniteEntry(entry), true, `entry ${entry.key} should have finite coordinates`)
    assert.equal(typeof entry.text, 'string', `entry ${entry.key} should carry text`)
    assert.equal(entry.text.length > 0, true, `entry ${entry.key} should not be empty`)
  }
})

test('invalid and empty input matrix does not produce false-positive entries', () => {
  const entries = buildVoucherTextPreviewEntries({
    voucherNo: '',
    budgetItem: '',
    amount: '12.34',
    purpose: '',
    receiptCount: '',
    payDate: '114.03.15',
  }, textConfig)

  assert.equal(entries.some(entry => String(entry.key).startsWith('voucherNo-')), false)
  assert.equal(entries.some(entry => entry.key === 'budgetItem'), false)
  assert.equal(entries.some(entry => entry.key === 'paymentAmount'), false)
  assert.equal(entries.some(entry => entry.key === 'payDate'), false)
  assert.equal(entries.some(entry => entry.key === 'purpose'), false)
  assert.equal(entries.some(entry => String(entry.key).startsWith('amount-')), false)
})
