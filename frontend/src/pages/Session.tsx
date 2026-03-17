import { useParams } from "react-router-dom";

export default function Session(): JSX.Element {
    const { id } = useParams<"id">();

    return (
        <main>
            <h1>Session</h1>
            <p>Active session placeholder for ID: {id ?? "unknown"}</p>
        </main>
    );
}