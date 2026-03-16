import axiosClient from "../../utils/aoxis";

export const useNOK = () => {
    const getNOKAll = async () => {
        const response = await axiosClient.get("/next-of-kin/all");
        return response.data;
    }
    const createNOK = async (next_of_kin_data) => {
        const response = await axiosClient.post("/next-of-kin/create", next_of_kin_data);
        return response.data;
    }
    const updateNOK = async (next_of_kin_id, next_of_kin_data) => {
        const response = await axiosClient.patch(`/next-of-kin/${next_of_kin_id}`, next_of_kin_data);
        return response.data;
    }
    const deleteNOK = async (next_of_kin_id) => {
        const response = await axiosClient.delete(`/next-of-kin/${next_of_kin_id}`);
        return response.data;
    }
    return { getNOKAll, createNOK, updateNOK, deleteNOK };
}