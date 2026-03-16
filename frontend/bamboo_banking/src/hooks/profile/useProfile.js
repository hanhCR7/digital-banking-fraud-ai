import axiosClient from "../../utils/aoxis";

export const useProfile = () => {
    const getProfile = async () => {
        const response = await axiosClient.get("/profile/me");
        return response.data;
    };
    const createProfile = async (profile_data) => {
        const response = await axiosClient.post("/profile/create", profile_data);
        return response.data;
    };
    const updateProfile = async (profile_data) => {
        const response = await axiosClient.patch("/profile/update", profile_data);
        return response.data;
    };
    const uploadProfilePhoto = async (image_type, file) => {
        const formData = new FormData();
        formData.append("file", file);
        const response = await axiosClient.post(`/profile/upload/${image_type}`, formData, {
            headers: { "Content-Type": "multipart/form-data" },
        });
        return response.data;
    };
    const getProfilePhotoStatus = async (task_id) => {
        const response = await axiosClient.get(`/profile/upload/${task_id}/status`);
        return response.data;
    };
    return { getProfile, createProfile, updateProfile, uploadProfilePhoto, getProfilePhotoStatus };
};