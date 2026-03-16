import axiosClient from "../../utils/aoxis";

export const useML = () => {
  const trainModelWithDefaults = async () => {
    const response = await axiosClient.post("/ml/train/default");
    return response.data;
  };

  const trainModel = async (payload) => {
    const response = await axiosClient.post("/ml/train", payload);
    return response.data;
  };

  const listModels = async (status, limit = 10) => {
    const response = await axiosClient.get("/ml/models", {
      params: { status, limit },
    });
    return response.data;
  };

  const getModelById = async (modelId) => {
    const response = await axiosClient.get(`/ml/models/${modelId}`);
    return response.data;
  };

  const getMLStatus = async () => {
    const response = await axiosClient.get("/ml/status");
    return response.data;
  };

  const evaluateModel = async (payload) => {
    const response = await axiosClient.post("/ml/evaluate", payload);
    return response.data;
  };

  const deployModel = async (payload) => {
    const response = await axiosClient.post("/ml/deploy", payload);
    return response.data;
  };

  const autoDeployBestModel = async (performanceThreshold = 0.0) => {
    const response = await axiosClient.post(
      "/ml/auto-deploy",
      null,
      { params: { performance_threshold: performanceThreshold } }
    );
    return response.data;
  };

  return {
    trainModelWithDefaults,
    trainModel,
    listModels,
    getModelById,
    getMLStatus,
    evaluateModel,
    deployModel,
    autoDeployBestModel,
  };
};