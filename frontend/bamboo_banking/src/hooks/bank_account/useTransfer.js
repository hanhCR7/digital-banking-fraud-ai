import axiosClient from "../../utils/aoxis";

export const useTransfer = () => {
    const initiateTransfer = async (transfer_data) => {
        const response = await axiosClient.post("/bank-account/transfer/initiate", transfer_data);
        return response.data;
    }
    const completeTransfer = async (transfer_data) => {
        const response = await axiosClient.post("/bank-account/transfer/complete", transfer_data);
        return response.data;
    }
    return { initiateTransfer, completeTransfer };
}