import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const targetPath = path.resolve(__dirname, '../src/views/VoucherTemplateConfigView.vue')

test('voucher template config uses canvas bringObjectToFront API', () => {
  const source = fs.readFileSync(targetPath, 'utf8')

  assert.equal(
    source.includes('.bringToFront('),
    false,
    'Do not call object.bringToFront; Fabric 7 uses canvas.bringObjectToFront(obj).',
  )

  assert.equal(
    source.includes('fabricCanvas.bringObjectToFront('),
    true,
    'Expected canvas-level bringObjectToFront call to keep labels above preview groups.',
  )
})
