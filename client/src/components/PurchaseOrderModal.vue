<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen && backlogItem" class="modal-overlay" @click="close">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h3 class="modal-title">
              {{ mode === 'view' ? t('purchaseOrder.viewTitle') : t('purchaseOrder.createTitle') }}
            </h3>
            <button class="close-button" :aria-label="t('purchaseOrder.close')" @click="close">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M15 5L5 15M5 5L15 15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <div class="item-summary">
              <div class="item-name">{{ translateProductName(backlogItem.item_name) }}</div>
              <div class="item-meta">
                SKU: {{ backlogItem.item_sku }}
                <span class="meta-sep">|</span>
                {{ t('purchaseOrder.shortage') }}: {{ shortage }} {{ t('purchaseOrder.units') }}
              </div>
            </div>

            <!-- View mode -->
            <template v-if="mode === 'view'">
              <div v-if="loadingPO" class="state-message">{{ t('purchaseOrder.loading') }}</div>
              <div v-else-if="error" class="error-message">{{ error }}</div>
              <div v-else-if="purchaseOrder" class="info-grid">
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.poId') }}</div>
                  <div class="info-value mono">{{ purchaseOrder.id }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.status') }}</div>
                  <div class="info-value"><span class="badge">{{ purchaseOrder.status }}</span></div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.supplierName') }}</div>
                  <div class="info-value">{{ purchaseOrder.supplier_name }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.quantity') }}</div>
                  <div class="info-value">{{ purchaseOrder.quantity }} {{ t('purchaseOrder.units') }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.unitCost') }}</div>
                  <div class="info-value">{{ formatMoney(purchaseOrder.unit_cost) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.total') }}</div>
                  <div class="info-value strong">{{ formatMoney(viewTotal) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.expectedDelivery') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.expected_delivery_date) }}</div>
                </div>
                <div class="info-item">
                  <div class="info-label">{{ t('purchaseOrder.createdDate') }}</div>
                  <div class="info-value">{{ formatDate(purchaseOrder.created_date) }}</div>
                </div>
                <div v-if="purchaseOrder.notes" class="info-item full">
                  <div class="info-label">{{ t('purchaseOrder.notes') }}</div>
                  <div class="info-value notes">{{ purchaseOrder.notes }}</div>
                </div>
              </div>
            </template>

            <!-- Create mode -->
            <form v-else id="po-form" novalidate @submit.prevent="submit">
              <div class="form-group">
                <label for="po-supplier">{{ t('purchaseOrder.supplierName') }}</label>
                <input
                  id="po-supplier"
                  v-model="form.supplier_name"
                  type="text"
                  class="form-input"
                  :placeholder="t('purchaseOrder.supplierPlaceholder')"
                />
                <div v-if="fieldErrors.supplier_name" class="field-error">{{ fieldErrors.supplier_name }}</div>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label for="po-quantity">{{ t('purchaseOrder.quantity') }}</label>
                  <input
                    id="po-quantity"
                    v-model.number="form.quantity"
                    type="number"
                    min="1"
                    step="1"
                    class="form-input"
                  />
                  <div v-if="fieldErrors.quantity" class="field-error">{{ fieldErrors.quantity }}</div>
                </div>
                <div class="form-group">
                  <label for="po-unit-cost">{{ t('purchaseOrder.unitCost') }} (USD)</label>
                  <input
                    id="po-unit-cost"
                    v-model.number="form.unit_cost"
                    type="number"
                    min="0"
                    step="0.01"
                    class="form-input"
                  />
                  <div v-if="fieldErrors.unit_cost" class="field-error">{{ fieldErrors.unit_cost }}</div>
                </div>
              </div>

              <div class="form-group">
                <label for="po-date">{{ t('purchaseOrder.expectedDelivery') }}</label>
                <input id="po-date" v-model="form.expected_delivery_date" type="date" class="form-input" />
                <div v-if="fieldErrors.expected_delivery_date" class="field-error">
                  {{ fieldErrors.expected_delivery_date }}
                </div>
              </div>

              <div class="form-group">
                <label for="po-notes">{{ t('purchaseOrder.notes') }}</label>
                <textarea
                  id="po-notes"
                  v-model="form.notes"
                  rows="3"
                  class="form-input"
                  :placeholder="t('purchaseOrder.notesPlaceholder')"
                ></textarea>
              </div>

              <div class="total-row">
                <span>{{ t('purchaseOrder.total') }}</span>
                <span class="total-value">{{ formatMoney(formTotal) }}</span>
              </div>

              <div v-if="error" class="error-message">{{ error }}</div>
            </form>
          </div>

          <div class="modal-footer">
            <button type="button" class="btn-secondary" @click="close">
              {{ mode === 'view' ? t('purchaseOrder.close') : t('purchaseOrder.cancel') }}
            </button>
            <button
              v-if="mode === 'create'"
              type="submit"
              form="po-form"
              class="btn-primary"
              :disabled="submitting"
            >
              {{ submitting ? t('purchaseOrder.submitting') : t('purchaseOrder.submit') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

const { t, currentLocale, translateProductName } = useI18n()

const props = defineProps({
  isOpen: { type: Boolean, default: false },
  backlogItem: { type: Object, default: null },
  mode: {
    type: String,
    default: 'create',
    validator: (value) => ['create', 'view'].includes(value)
  }
})

const emit = defineEmits(['close', 'po-created'])

const form = reactive({
  supplier_name: '',
  quantity: 1,
  unit_cost: null,
  expected_delivery_date: '',
  notes: ''
})
const fieldErrors = reactive({})
const error = ref(null)
const submitting = ref(false)
const purchaseOrder = ref(null)
const loadingPO = ref(false)

const shortage = computed(() => {
  if (!props.backlogItem) return 0
  return Math.max(0, props.backlogItem.quantity_needed - props.backlogItem.quantity_available)
})

const formTotal = computed(() => {
  const qty = Number(form.quantity)
  const cost = Number(form.unit_cost)
  return Number.isFinite(qty) && Number.isFinite(cost) ? qty * cost : 0
})

// Total is not part of the API payload, so derive it from quantity * unit_cost
const viewTotal = computed(() => {
  if (!purchaseOrder.value) return 0
  return purchaseOrder.value.quantity * purchaseOrder.value.unit_cost
})

const resetForm = () => {
  form.supplier_name = ''
  // Default to the shortage, but never below the minimum order of 1
  form.quantity = Math.max(1, shortage.value)
  form.unit_cost = null
  form.expected_delivery_date = ''
  form.notes = ''
  Object.keys(fieldErrors).forEach((key) => delete fieldErrors[key])
  error.value = null
  submitting.value = false
}

const loadPO = async () => {
  purchaseOrder.value = null
  error.value = null
  loadingPO.value = true
  // Capture the id so a slow response for a previous item cannot overwrite the current one
  const requestedId = props.backlogItem.id
  try {
    const data = await api.getPurchaseOrderByBacklogItem(requestedId)
    if (props.backlogItem?.id === requestedId) purchaseOrder.value = data
  } catch (err) {
    if (props.backlogItem?.id === requestedId) {
      error.value = err.response?.data?.detail || t('purchaseOrder.loadFailed')
    }
    console.error('Failed to load purchase order:', err)
  } finally {
    if (props.backlogItem?.id === requestedId) loadingPO.value = false
  }
}

// Re-initialise every time the modal opens (or switches item/mode) so stale
// form input or a previous item's PO is never shown.
watch(
  () => [props.isOpen, props.backlogItem?.id, props.mode],
  () => {
    if (!props.isOpen || !props.backlogItem) return
    if (props.mode === 'view') {
      loadPO()
    } else {
      resetForm()
    }
  },
  { immediate: true }
)

const validate = () => {
  Object.keys(fieldErrors).forEach((key) => delete fieldErrors[key])
  if (!form.supplier_name.trim()) fieldErrors.supplier_name = t('purchaseOrder.supplierRequired')
  if (!Number.isInteger(form.quantity) || form.quantity < 1) fieldErrors.quantity = t('purchaseOrder.quantityInvalid')
  // v-model.number leaves '' for an empty field, which Number() would treat as 0
  if (typeof form.unit_cost !== 'number' || !(form.unit_cost > 0)) fieldErrors.unit_cost = t('purchaseOrder.unitCostInvalid')
  if (!form.expected_delivery_date) fieldErrors.expected_delivery_date = t('purchaseOrder.dateRequired')
  return Object.keys(fieldErrors).length === 0
}

const submit = async () => {
  if (submitting.value || !validate()) return
  submitting.value = true
  error.value = null
  try {
    const created = await api.createPurchaseOrder({
      backlog_item_id: props.backlogItem.id,
      supplier_name: form.supplier_name.trim(),
      quantity: form.quantity,
      unit_cost: form.unit_cost,
      expected_delivery_date: form.expected_delivery_date,
      notes: form.notes.trim() || null
    })
    emit('po-created', created)
  } catch (err) {
    // FastAPI returns detail as a string (400/404) or a list of objects (422)
    const detail = err.response?.data?.detail
    error.value = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg).join('; ')
        : t('purchaseOrder.createFailed')
    console.error('Failed to create purchase order:', err)
  } finally {
    submitting.value = false
  }
}

const close = () => {
  emit('close')
}

// PO amounts are entered and stored in USD, so always display them in USD
const formatMoney = (amount) => {
  const value = Number(amount)
  if (!Number.isFinite(value)) return 'N/A'
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

const formatDate = (dateString) => {
  if (!dateString) return 'N/A'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return 'N/A'
  return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal-container {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.15);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.modal-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.close-button {
  background: none;
  border: none;
  color: #64748b;
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.close-button:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.item-summary {
  padding: 1rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 1.5rem;
}

.item-name {
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 0.25rem;
}

.item-meta {
  font-size: 0.813rem;
  color: #64748b;
}

.meta-sep {
  margin: 0 0.5rem;
  color: #cbd5e1;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.form-group label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.form-input {
  padding: 0.625rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.938rem;
  font-family: inherit;
  color: #0f172a;
  background: white;
  resize: vertical;
}

.form-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.field-error {
  font-size: 0.813rem;
  color: #dc2626;
}

.total-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 0.75rem 0;
  border-top: 1px solid #e2e8f0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
}

.total-value {
  font-size: 1.25rem;
  color: #0f172a;
}

.error-message {
  margin-top: 0.5rem;
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 0.875rem;
}

.state-message {
  color: #64748b;
  font-size: 0.875rem;
  padding: 1rem 0;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}

.info-item.full {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #64748b;
}

.info-value {
  font-size: 0.938rem;
  color: #0f172a;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.info-value.mono {
  font-family: 'Monaco', 'Courier New', monospace;
  color: #2563eb;
}

.info-value.strong {
  font-weight: 700;
}

.info-value.notes {
  white-space: pre-wrap;
  font-weight: 400;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 6px;
  background: #dbeafe;
  color: #1e40af;
  font-size: 0.813rem;
  font-weight: 600;
  text-transform: capitalize;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}

.btn-secondary,
.btn-primary {
  padding: 0.625rem 1.25rem;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.btn-secondary {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.btn-secondary:hover {
  background: #e2e8f0;
  border-color: #cbd5e1;
}

.btn-primary {
  background: #3b82f6;
  border: 1px solid #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
}

.btn-primary:disabled {
  background: #cbd5e1;
  border-color: #cbd5e1;
  cursor: not-allowed;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95);
}
</style>
