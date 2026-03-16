import axiosClient from "../../utils/aoxis";

export const useCard = () => {
    const createCard = async (card_data) => {
        const response = await axiosClient.post("/virtual-card/create", card_data);
        return response.data;
    }
    const activateCard = async (card_id) => {
        const response = await axiosClient.patch(`/virtual-card/${card_id}/activate`);
        return response.data;
    }
    const topUpCard = async (card_data) => {
        const response = await axiosClient.post(`/virtual-card/${card_id}/top-up`, card_data);
        return response.data;
    }
    const blockCard = async (card_id, block_reason, block_reason_description) => {
        const response = await axiosClient.patch(`/virtual-card/${card_id}/block`, {
            block_reason,
            block_reason_description,
        });
        return response.data;
    }
    const deleteCard = async (card_id) => {
        const response = await axiosClient.delete(`/virtual-card/${card_id}`);
        return response.data;
    }
    return { createCard, activateCard, topUpCard, blockCard, deleteCard };
}