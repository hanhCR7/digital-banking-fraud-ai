import axiosClient from "../../utils/aoxis";

export const useActiveAccount = () => {
    const activeAccount = async (token) => {
        const response = await axiosClient.get(`/auth/activate/${token}`);
        return response.data;
    }
    const resendActivation = async (email) => {
        const response = await axiosClient.post("/auth/resend-activation-link", {
            email,
        });
        return response.data;
    }
    return { activeAccount, resendActivation };
}