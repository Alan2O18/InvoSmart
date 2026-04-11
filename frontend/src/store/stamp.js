import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export const useStampStore = defineStore('stamp', () => {
  const stamps = ref([])
  const loading = ref(false)
  const detecting = ref(false)
  const saving = ref(false)
  const error = ref('')

  const fetchStamps = async () => {
    loading.value = true
    error.value = ''
    try {
      const res = await api.listStamps()
      stamps.value = Array.isArray(res.data) ? res.data : []
      return stamps.value
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message || String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  const detectStamps = async (file, mode = 'red') => {
    detecting.value = true
    error.value = ''
    try {
      const res = await api.detectStamps(file, mode)
      return res.data
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message || String(e)
      throw e
    } finally {
      detecting.value = false
    }
  }

  const registerStamps = async (file, mode, selections) => {
    saving.value = true
    error.value = ''
    try {
      const res = await api.registerStamps(file, mode, selections)
      await fetchStamps()
      return res.data
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message || String(e)
      throw e
    } finally {
      saving.value = false
    }
  }

  const deleteStamp = async (stampId) => {
    loading.value = true
    error.value = ''
    try {
      await api.deleteStampById(stampId)
      stamps.value = stamps.value.filter((item) => item.id !== stampId)
    } catch (e) {
      error.value = e?.response?.data?.detail || e.message || String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    stamps,
    loading,
    detecting,
    saving,
    error,
    fetchStamps,
    detectStamps,
    registerStamps,
    deleteStamp,
  }
})
