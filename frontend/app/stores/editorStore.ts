import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  AgentMessage,
  Character,
  Shot,
  WorkflowStage,
} from "~/types";

interface EditorState {
  // Selection state
  selectedShotId: number | null;
  selectedCharacterId: number | null;
  highlightedMessageIndex: number | null;

  // Agent state
  isGenerating: boolean;
  currentStage: WorkflowStage;
  currentAgent: string | null;
  progress: number;
  messages: AgentMessage[];

  // 确认状态
  awaitingConfirm: boolean;
  awaitingAgent: string | null;
  currentRunId: number | null;

  // 自动模式
  autoMode: boolean;

  // Data cache
  characters: Character[];
  shots: Shot[];
  projectVideoUrl: string | null;  // 最终拼接视频 URL
  projectUpdatedAt: number | null; // 项目更新时间戳（用于触发刷新）
  currentProjectId: number | null; // 当前项目 ID，用于判断是否切换项目

  // Actions
  setSelectedShot: (id: number | null) => void;
  setSelectedCharacter: (id: number | null) => void;
  setHighlightedMessage: (index: number | null) => void;
  setGenerating: (isGenerating: boolean) => void;
  setCurrentStage: (stage: WorkflowStage) => void;
  setCurrentAgent: (agent: string | null) => void;
  setProgress: (progress: number) => void;
  addMessage: (message: AgentMessage) => void;
  setMessages: (messages: AgentMessage[]) => void;
  clearMessages: () => void;
  setCharacters: (characters: Character[]) => void;
  setShots: (shots: Shot[]) => void;
  setProjectVideoUrl: (url: string | null) => void;
  setProjectUpdatedAt: (timestamp: number) => void;
  setCurrentProjectId: (id: number | null) => void;
  setAwaitingConfirm: (awaiting: boolean, agent?: string | null, runId?: number | null) => void;
  setCurrentRunId: (runId: number | null) => void;
  setAutoMode: (autoMode: boolean) => void;
  // 精细化控制 Actions
  updateCharacter: (character: Character) => void;
  updateShot: (shot: Shot) => void;
  removeCharacter: (characterId: number) => void;
  removeShot: (shotId: number) => void;
  reset: () => void;
}

const initialState = {
  selectedShotId: null,
  selectedCharacterId: null,
  highlightedMessageIndex: null,
  isGenerating: false,
  currentStage: "ideate" as WorkflowStage,
  currentAgent: null,
  progress: 0,
  messages: [],
  awaitingConfirm: false,
  awaitingAgent: null,
  currentRunId: null,
  autoMode: false,
  characters: [],
  shots: [],
  projectVideoUrl: null,
  projectUpdatedAt: null,
  currentProjectId: null,
};

export const useEditorStore = create<EditorState>()(
  persist(
    (set) => ({
      ...initialState,

      setSelectedShot: (id) => set({ selectedShotId: id }),
      setSelectedCharacter: (id) => set({ selectedCharacterId: id }),
      setHighlightedMessage: (index) => set({ highlightedMessageIndex: index }),
      setGenerating: (isGenerating) => set({ isGenerating }),
      setCurrentStage: (stage) => set({ currentStage: stage }),
      setCurrentAgent: (agent) => set({ currentAgent: agent }),
      setProgress: (progress) => set({ progress }),
      addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),
      setMessages: (messages) => set({ messages }),
      clearMessages: () => set({ messages: [], highlightedMessageIndex: null }),
      setCharacters: (characters) => set({ characters }),
      setShots: (shots) => set({ shots }),
      setProjectVideoUrl: (url) => set({ projectVideoUrl: url }),
      setProjectUpdatedAt: (timestamp) => set({ projectUpdatedAt: timestamp }),
      setCurrentProjectId: (id) => set({ currentProjectId: id }),
      setAwaitingConfirm: (awaiting, agent = null, runId) =>
        set((state) => ({
          awaitingConfirm: awaiting,
          awaitingAgent: agent,
          currentRunId: runId !== undefined ? runId : state.currentRunId
        })),
      setCurrentRunId: (runId) => set({ currentRunId: runId }),
      setAutoMode: (autoMode) => set({ autoMode }),
      // 精细化控制 Actions
      updateCharacter: (character) =>
        set((state) => ({
          characters: state.characters.map((c) =>
            c.id === character.id ? character : c
          ),
        })),
      updateShot: (shot) =>
        set((state) => ({
          shots: state.shots.map((s) =>
            s.id === shot.id ? shot : s
          ),
        })),
      removeCharacter: (characterId) =>
        set((state) => ({
          characters: state.characters.filter((c) => c.id !== characterId),
        })),
      removeShot: (shotId) =>
        set((state) => ({
          shots: state.shots.filter((s) => s.id !== shotId),
        })),
      reset: () => set(initialState),
    }),
    {
      name: "editor-storage", // localStorage 中的键名
      partialize: (state) => ({
        autoMode: state.autoMode,
        currentProjectId: state.currentProjectId,
        currentStage: state.currentStage,
        currentAgent: state.currentAgent,
        isGenerating: state.isGenerating,
        progress: state.progress,
        awaitingConfirm: state.awaitingConfirm,
        awaitingAgent: state.awaitingAgent,
        currentRunId: state.currentRunId,
      }), // 持久化关键状态，以便刷新后恢复
    }
  )
);
