// Shared, mutable app state.
export const state = {
  currentConversationId: null,
  imageMode: false,
  imageStyle: "realistic",
  pendingFile: null, // file attached to the composer, uploaded together with the next send
};