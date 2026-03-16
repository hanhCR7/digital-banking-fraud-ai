import axiosClient from "../../utils/aoxis";

export const useBankAccount = () => {
    const createBankAccount = async (bank_account_data) => {
        const response = await axiosClient.post("/bank-account/create", bank_account_data);
        return response.data;
    }
    const activateBankAccount = async (account_id) => {
        const response = await axiosClient.patch(`/bank-account/${account_id}/activate`);
        return response.data;
    }
    return { createBankAccount, activateBankAccount };
}