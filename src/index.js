exports.handler = async (event) => {
  return {
    statusCode: 200,
    headers: {
      "Content-Type": "text/plain"
    },
    body: "Mera naam Lambda hai! Aap sab kaise hain. Mein shubham loda hoon",
  };
};
