<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading && !recommendations" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error && !recommendations" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget card -->
      <div class="card budget-card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budget') }}</h3>
        </div>
        <div class="budget-display">
          {{ currencySymbol }}{{ budget.toLocaleString() }}
        </div>
        <input
          type="range"
          min="1000"
          max="100000"
          step="1000"
          v-model.number="budget"
          class="budget-slider"
        />
        <div v-if="recommendations" class="summary-row">
          <div class="summary-item">
            <span class="summary-label">{{ t('restocking.fullRestockCost') }}</span>
            <span class="summary-value">{{ currencySymbol }}{{ recommendations.full_restock_cost.toLocaleString() }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">{{ t('restocking.allocated') }}</span>
            <span class="summary-value">{{ currencySymbol }}{{ recommendations.total_cost.toLocaleString() }}</span>
          </div>
          <div class="summary-item">
            <span class="summary-label">{{ t('restocking.itemsToRestock') }}</span>
            <span class="summary-value">{{ recommendations.items.length }}</span>
          </div>
          <div v-if="recommendations.scaled" class="summary-item">
            <span class="summary-label">&nbsp;</span>
            <span class="badge warning">{{ t('restocking.scaled') }}</span>
          </div>
        </div>
      </div>

      <!-- Recommendations card -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            {{ t('restocking.recommendations') }}
            <span v-if="recommendations">({{ recommendations.items.length }})</span>
          </h3>
        </div>

        <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
        <div v-else-if="!recommendations || recommendations.items.length === 0" class="empty-state">
          {{ t('restocking.noItems') }}
        </div>
        <div v-else class="table-container">
          <table>
            <thead>
              <tr>
                <th>{{ t('restocking.table.sku') }}</th>
                <th>{{ t('restocking.table.name') }}</th>
                <th>{{ t('restocking.table.category') }}</th>
                <th>{{ t('restocking.table.onHand') }}</th>
                <th>{{ t('restocking.table.reorderPoint') }}</th>
                <th>{{ t('restocking.table.recommendedQty') }}</th>
                <th>{{ t('restocking.table.unitCost') }}</th>
                <th>{{ t('restocking.table.lineCost') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in recommendations.items" :key="item.sku">
                <td><strong>{{ item.sku }}</strong></td>
                <td>{{ item.name }}</td>
                <td>{{ item.category }}</td>
                <td>{{ item.quantity_on_hand }}</td>
                <td>{{ item.reorder_point }}</td>
                <td><strong>{{ item.recommended_quantity }}</strong></td>
                <td>{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                <td><strong>{{ currencySymbol }}{{ item.line_cost.toLocaleString() }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="action-row">
          <div v-if="error" class="error action-error">{{ error }}</div>
          <div v-if="placedOrder" class="success-banner">
            <span>{{ t('restocking.orderSuccess', { orderNumber: placedOrder.order_number, days: placedOrder.lead_time_days }) }}</span>
            <router-link to="/orders">{{ t('restocking.viewOrders') }}</router-link>
          </div>
          <button
            class="btn-primary"
            :disabled="submitting || !recommendations || recommendations.items.length === 0"
            @click="placeOrder"
          >
            {{ submitting ? t('restocking.placingOrder') : t('restocking.placeOrder') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()
    const currencySymbol = computed(() => currentCurrency.value === 'JPY' ? '¥' : '$')

    const budget = ref(25000)
    const recommendations = ref(null)
    const loading = ref(true)
    const submitting = ref(false)
    const error = ref(null)
    const placedOrder = ref(null)

    let debounceTimer = null
    const loadRecommendations = async () => {
      try {
        loading.value = true
        error.value = null
        recommendations.value = await api.getRestockRecommendations(budget.value)
      } catch (err) {
        error.value = 'Failed to load recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    watch(budget, () => {
      placedOrder.value = null
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(loadRecommendations, 300)
    })

    const placeOrder = async () => {
      try {
        submitting.value = true
        error.value = null
        placedOrder.value = await api.createRestockOrder(budget.value)
      } catch (err) {
        error.value = 'Failed to place order: ' + err.message
      } finally {
        submitting.value = false
      }
    }

    onMounted(loadRecommendations)

    return {
      t,
      currencySymbol,
      budget,
      recommendations,
      loading,
      submitting,
      error,
      placedOrder,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-display {
  font-size: 2.5rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 1rem;
}

.budget-slider {
  width: 100%;
  height: 6px;
  appearance: none;
  -webkit-appearance: none;
  background: #e2e8f0;
  border-radius: 3px;
  outline: none;
  cursor: pointer;
  margin-bottom: 1.5rem;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #0f172a;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.budget-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #0f172a;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.budget-slider::-webkit-slider-runnable-track {
  background: #e2e8f0;
  border-radius: 3px;
  height: 6px;
}

.budget-slider::-moz-range-track {
  background: #e2e8f0;
  border-radius: 3px;
  height: 6px;
}

.summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  align-items: flex-end;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-value {
  font-size: 1.125rem;
  font-weight: 700;
  color: #0f172a;
}

.empty-state {
  padding: 2rem;
  text-align: center;
  color: #64748b;
  font-size: 0.9375rem;
}

.action-row {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem 1.5rem;
  border-top: 1px solid #f1f5f9;
}

.action-error {
  width: 100%;
  font-size: 0.875rem;
}

.success-banner {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  background: #dcfce7;
  color: #15803d;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.success-banner a {
  color: #15803d;
  font-weight: 600;
  text-decoration: underline;
  white-space: nowrap;
}

.success-banner a:hover {
  color: #166534;
}

.btn-primary {
  background: #0f172a;
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.625rem 1.5rem;
  font-size: 0.9375rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, opacity 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #1e293b;
}

.btn-primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
