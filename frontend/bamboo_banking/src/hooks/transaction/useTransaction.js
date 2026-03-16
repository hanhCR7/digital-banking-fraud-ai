// hooks/transaction/useTransaction.ts
import { useCallback } from "react";
import axiosClient from "../../utils/aoxis";

export const useTransaction = () => {
  const getTransactionMetrics = useCallback(async () => {
    const res = await axiosClient.get("/transaction/metrics");
    return res.data;
  }, []);

  const getTransactionTrend = useCallback(async () => {
    const res = await axiosClient.get("/transaction/charts");
    return res.data;
  }, []);

  const getAllUserTransactionHistory = useCallback(async (params) => {
    const res = await axiosClient.get("/transactions/all-user/history", {
      params,
    });
    return res.data;
  }, []);

  const getAllUserRiskHistory = useCallback(async (params) => {
    const res = await axiosClient.get("/transaction/risk-history/all-user", {
      params,
    });
    return res.data;
  }, []);

  const reviewTransaction = useCallback(async (transactionId, payload) => {
    const res = await axiosClient.post(
      `/transaction/${transactionId}/review`,
      payload,
    );
    return res.data;
  }, []);

  return {
    getTransactionMetrics,
    getTransactionTrend,
    getAllUserTransactionHistory,
    getAllUserRiskHistory,
    reviewTransaction,
  };
};
