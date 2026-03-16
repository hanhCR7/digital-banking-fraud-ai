import axiosClient from "../../utils/aoxis";

export const useWithdraw = () => {
    const withdraw = async (account_number, amount, username, description, idempotency_key) => {
        const response = await axiosLogin.post("/bank-account/withdraw", {
            account_number,
            amount,
            username,
            description,
            idempotency_key,
        });
        return response.data;
    }
    return { withdraw };
}