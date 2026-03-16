import axiosClient from "../../utils/aoxis";

export const useAuth = () => {
    const login = async (email, password) => {
        const response = await axiosClient.post("/auth/login/request-otp", {
            email,
            password,
        });
        return response.data;
    };
    const verifyOtp = async (email, otp) => {
        const response = await axiosClient.post("/auth/login/verify-otp", {
            email,
            otp,
        });
        return response.data;
    };
    const logout = async () => {
        const response = await axiosClient.post("/auth/logout");
        return response.data;
    };
    const register = async (payload) => {
        const response = await axiosClient.post("/auth/register", payload);
        return response.data;
    };
    const resetPassword = async (email) => {
        const response = await axiosClient.post("/auth/request-password-reset", {
            email,
        });
        return response.data;
    };
    const resetPasswordWithToken = async (token, new_password, confirm_password) => {
        const response = await axiosClient.post(`/auth/reset-password/${token}`, {
            new_password,
            confirm_password,
        });
        return response.data;
    };
    const changePassword = async (current_password, new_password, confirm_password) => {
        const response = await axiosClient.post("/auth/change-password", {
            current_password,
            new_password,
            confirm_password,
        });
        return response.data;
    };
    const changeInitialPassword = async (user_id, new_password, confirm_password) => {
        const response = await axiosClient.post("/auth/change-initial-password", {
            user_id,
            new_password,
            confirm_password,
        });
        return response.data;
    };
    return {
        login,
        verifyOtp,
        logout,
        register,
        resetPassword,
        resetPasswordWithToken,
        changePassword,
        changeInitialPassword,
    };
};