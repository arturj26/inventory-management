<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="card budget-card">
        <div class="budget-header">
          <label for="budget-slider" class="stat-label">{{ t('restocking.budget') }}</label>
          <div class="budget-value">{{ formatCurrency(budget, currentCurrency) }}</div>
        </div>
        <input
          id="budget-slider"
          v-model.number="budget"
          type="range"
          class="budget-slider"
          min="0"
          :max="budgetMax"
          :step="BUDGET_STEP"
          :aria-valuetext="formatCurrency(budget, currentCurrency)"
          :style="{ '--fill': budgetMax ? `${(budget / budgetMax) * 100}%` : '0%' }"
        />
        <div class="budget-scale">
          <span>{{ formatCurrency(0, currentCurrency) }}</span>
          <span>{{ t('restocking.budgetCoverage', { percent: coveragePercent, total: formatCurrency(totalNeeded, currentCurrency) }) }}</span>
          <span>{{ formatCurrency(budgetMax, currentCurrency) }}</span>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.orderTotal') }}</div>
          <div class="stat-value">{{ formatCurrency(orderTotal, currentCurrency) }}</div>
        </div>
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.remainingBudget') }}</div>
          <div class="stat-value">{{ formatCurrency(budget - orderTotal, currentCurrency) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsToOrder') }}</div>
          <div class="stat-value">{{ orderLines.length }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.leadTime') }}</div>
          <div class="stat-value">{{ orderLines.length ? t('restocking.days', { count: orderLeadTime }) : '–' }}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title">{{ t('restocking.recommendedItems') }} ({{ recommendations.length }})</h3>
            <p class="card-note">{{ t('restocking.rankingNote') }}</p>
          </div>
          <button
            class="place-order-btn"
            :disabled="!orderLines.length || placing"
            @click="placeOrder"
          >
            {{ placing ? t('restocking.placing') : t('restocking.placeOrder') }}
          </button>
        </div>

        <div v-if="placedOrder" class="notice success" role="status">
          {{ t('restocking.orderPlaced', { number: placedOrder.order_number, date: formatDate(placedOrder.expected_delivery) }) }}
          <router-link to="/orders">{{ t('restocking.viewInOrders') }}</router-link>
        </div>
        <div v-if="placeError" class="notice danger" role="alert">{{ placeError }}</div>

        <p v-if="!recommendations.length" class="empty">{{ t('restocking.noShortfall') }}</p>
        <template v-else>
          <p v-if="!orderLines.length" class="empty">{{ t('restocking.noItemsInBudget') }}</p>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.itemName') }}</th>
                  <th>{{ t('restocking.table.trend') }}</th>
                  <th class="num">{{ t('restocking.table.forecastedDemand') }}</th>
                  <th class="num">{{ t('restocking.table.onHand') }}</th>
                  <th class="num">{{ t('restocking.table.shortfall') }}</th>
                  <th class="num">{{ t('restocking.table.orderQty') }}</th>
                  <th class="num">{{ t('restocking.table.unitCost') }}</th>
                  <th class="num">{{ t('restocking.table.lineTotal') }}</th>
                  <th class="num">{{ t('restocking.table.leadTime') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in recommendations" :key="item.item_sku" :class="{ excluded: item.orderQty === 0 }">
                  <td><strong>{{ item.item_sku }}</strong></td>
                  <td>{{ translateProductName(item.item_name) }}</td>
                  <td><span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span></td>
                  <td class="num">{{ item.forecasted_demand.toLocaleString() }}</td>
                  <td class="num">{{ item.onHand.toLocaleString() }}</td>
                  <td class="num">{{ item.shortfall.toLocaleString() }}</td>
                  <td class="num">
                    <strong>{{ item.orderQty.toLocaleString() }}</strong>
                    <span v-if="item.orderQty === 0" class="tag muted">{{ t('restocking.overBudget') }}</span>
                    <span v-else-if="item.orderQty < item.shortfall" class="tag partial">{{ t('restocking.partial') }}</span>
                  </td>
                  <td class="num">{{ formatCurrencyWithDecimals(item.unit_cost, currentCurrency, 2) }}</td>
                  <td class="num">{{ formatCurrency(item.lineTotal, currentCurrency) }}</td>
                  <td class="num">{{ t('restocking.days', { count: item.lead_time_days }) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency, formatCurrencyWithDecimals } from '../utils/currency'

const BUDGET_STEP = 500
const TREND_RANK = { increasing: 0, stable: 1, decreasing: 2 }

export default {
  name: 'Restocking',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName } = useI18n()

    const loading = ref(true)
    const error = ref(null)
    const forecasts = ref([])
    const inventoryItems = ref([])
    const budget = ref(0)

    const placing = ref(false)
    const placedOrder = ref(null)
    const placeError = ref(null)

    // Items whose forecasted demand exceeds stock, ranked by restocking priority
    const needs = computed(() => {
      const stockBySku = {}
      for (const item of inventoryItems.value) {
        stockBySku[item.sku] = (stockBySku[item.sku] || 0) + item.quantity_on_hand
      }

      return forecasts.value
        .map(forecast => {
          const onHand = stockBySku[forecast.item_sku] || 0
          return {
            ...forecast,
            onHand,
            shortfall: Math.max(forecast.forecasted_demand - onHand, 0)
          }
        })
        .filter(item => item.shortfall > 0)
        .sort((a, b) =>
          (TREND_RANK[a.trend] ?? 3) - (TREND_RANK[b.trend] ?? 3) || b.shortfall - a.shortfall
        )
    })

    const totalNeeded = computed(() => {
      return needs.value.reduce((sum, item) => sum + item.shortfall * item.unit_cost, 0)
    })

    const budgetMax = computed(() => {
      return Math.ceil(totalNeeded.value / BUDGET_STEP) * BUDGET_STEP
    })

    const coveragePercent = computed(() => {
      if (!totalNeeded.value) return 100
      return Math.min(Math.round((budget.value / totalNeeded.value) * 100), 100)
    })

    // Fill the budget greedily down the ranked list; work in cents to avoid float drift
    const recommendations = computed(() => {
      let remainingCents = Math.round(budget.value * 100)

      return needs.value.map(item => {
        const unitCents = Math.round(item.unit_cost * 100)
        const orderQty = Math.min(item.shortfall, Math.floor(remainingCents / unitCents))
        remainingCents -= orderQty * unitCents
        return { ...item, orderQty, lineTotal: (orderQty * unitCents) / 100 }
      })
    })

    const orderLines = computed(() => recommendations.value.filter(item => item.orderQty > 0))

    const orderTotal = computed(() => {
      return orderLines.value.reduce((sum, item) => sum + item.lineTotal, 0)
    })

    const orderLeadTime = computed(() => {
      return Math.max(0, ...orderLines.value.map(item => item.lead_time_days))
    })

    const loadData = async () => {
      try {
        loading.value = true
        const [forecastData, inventoryData] = await Promise.all([
          api.getDemandForecasts(),
          api.getInventory()
        ])
        forecasts.value = forecastData
        inventoryItems.value = inventoryData

        // Start halfway so the slider has room to move both ways
        budget.value = Math.round(budgetMax.value / 2 / BUDGET_STEP) * BUDGET_STEP
      } catch (err) {
        error.value = 'Failed to load restocking data: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (!orderLines.value.length || placing.value) return

      try {
        placing.value = true
        placeError.value = null
        placedOrder.value = await api.createRestockingOrder({
          budget: budget.value,
          items: orderLines.value.map(item => ({ sku: item.item_sku, quantity: item.orderQty }))
        })
      } catch (err) {
        placedOrder.value = null
        placeError.value = `${t('restocking.orderFailed')}: ${err.response?.data?.detail || err.message}`
      } finally {
        placing.value = false
      }
    }

    const formatDate = (dateString) => {
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Date(dateString).toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    // The page background lives on <body>, so switch it only while this view is shown
    onMounted(() => {
      document.body.classList.add('restocking-page')
      loadData()
    })

    onUnmounted(() => {
      document.body.classList.remove('restocking-page')
    })

    return {
      t,
      BUDGET_STEP,
      loading,
      error,
      budget,
      budgetMax,
      totalNeeded,
      coveragePercent,
      recommendations,
      orderLines,
      orderTotal,
      orderLeadTime,
      placing,
      placedOrder,
      placeError,
      placeOrder,
      formatDate,
      formatCurrency,
      formatCurrencyWithDecimals,
      currentCurrency,
      translateProductName
    }
  }
}
</script>

<style scoped>
/* Page, header and stat-card colors come from the global styles in App.vue */
.loading {
  color: #64748b;
}

.stat-card:hover {
  animation: tile-bounce 0.7s cubic-bezier(0.28, 0.84, 0.42, 1);
}

@keyframes tile-bounce {
  0% { transform: translateY(0); }
  30% { transform: translateY(-12px); }
  50% { transform: translateY(0); }
  68% { transform: translateY(-5px); }
  84% { transform: translateY(0); }
  92% { transform: translateY(-2px); }
  100% { transform: translateY(0); }
}

.budget-card {
  padding: 1.5rem;
  background: white;
  border: 1px solid #e2e8f0;
}

.budget-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 1rem;
}

.budget-header .stat-label {
  margin-bottom: 0;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
}

.budget-slider {
  width: 100%;
  height: 8px;
  appearance: none;
  border-radius: 999px;
  background: linear-gradient(to right, #3b82f6 var(--fill), #e2e8f0 var(--fill));
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  appearance: none;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #3b82f6;
  border: 3px solid #ffffff;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.25);
}

.budget-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #3b82f6;
  border: 3px solid #ffffff;
}

.budget-slider:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 4px;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.75rem;
  font-size: 0.813rem;
  color: #64748b;
}

.card-note {
  margin-top: 0.25rem;
  font-size: 0.813rem;
  color: #64748b;
}

.place-order-btn {
  padding: 0.625rem 1.25rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.notice {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.notice a {
  margin-left: 0.5rem;
  color: inherit;
  font-weight: 600;
}

.notice.success {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
}

.notice.danger {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.empty {
  color: #64748b;
  font-size: 0.875rem;
  padding: 0.5rem 0 1rem;
}

th.num,
td.num {
  text-align: right;
  white-space: nowrap;
}

tr.excluded td {
  color: #94a3b8;
}

.tag {
  display: inline-block;
  margin-left: 0.375rem;
  padding: 0.063rem 0.5rem;
  border-radius: 999px;
  font-size: 0.688rem;
  font-weight: 600;
}

.tag.partial {
  background: #fed7aa;
  color: #92400e;
}

.tag.muted {
  background: #f1f5f9;
  color: #64748b;
}

@media (prefers-reduced-motion: reduce) {
  .place-order-btn {
    transition: none;
  }

  .stat-card {
    animation: none;
  }
}
</style>
