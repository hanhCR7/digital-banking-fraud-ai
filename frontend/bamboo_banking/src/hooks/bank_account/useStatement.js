import axiosClient from "../../utils/aoxis";

export const useStatement = () => {
    const generateStatement = async (start_date, end_date, account_number) => {
        const response = await axiosClient.post("/bank-account/statement/generate", {
            start_date,
            end_date,
            account_number,
        });
        return response.data;
    }
    const downFileStatement = async (statement_id) => {
        const response = await axiosClient.get(`/bank-account/statement/${statement_id}`);
        return response.data;
    }
    return { generateStatement, downFileStatement };
}