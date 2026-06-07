//
//  ContentView.swift
//  Idea Evolution Engine
//
//  Created by Lisul Elvitigala on 6/7/26.
//

import SwiftUI
import Foundation
import AppKit
import Combine

private let backendWorkerCount = 4

struct ContentView: View {
    @State private var selectedSection: SidebarSection? = .workspace
    @StateObject private var viewModel = EvolutionViewModel()

    var body: some View {
        NavigationSplitView {
            SidebarView(selectedSection: $selectedSection, viewModel: viewModel)
                .navigationSplitViewColumnWidth(min: 220, ideal: 248, max: 280)
                .background(.thinMaterial)
        } detail: {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    HeaderView()

                    HStack(alignment: .top, spacing: 20) {
                        ParameterForm(viewModel: viewModel)
                            .frame(minWidth: 300, idealWidth: 360, maxWidth: 420)

                        VStack(spacing: 16) {
                            ProgressTracker(stage: viewModel.stage, progress: viewModel.progress)
                            ScoreSummary(response: viewModel.response)
                            DiagnosticsPanel(diagnostics: viewModel.diagnostics)
                        }
                        .frame(maxWidth: .infinity)
                    }

                    IdeasGrid(ideas: viewModel.response?.ideas ?? [])
                }
                .padding(24)
            }
            .background(Color(nsColor: .windowBackgroundColor))
        }
        .frame(minWidth: 980, minHeight: 680)
    }
}

private enum SidebarSection: String, CaseIterable, Identifiable {
    case workspace = "Workspace"
    case status = "Generation Status"
    case scoring = "Native Scoring"
    case diagnostics = "Diagnostics"

    var id: String { rawValue }

    var symbol: String {
        switch self {
        case .workspace: return "square.grid.2x2"
        case .status: return "waveform.path.ecg"
        case .scoring: return "cpu"
        case .diagnostics: return "stethoscope"
        }
    }
}

private enum ProcessStage: String, CaseIterable {
    case idle = "Ready"
    case queued = "Queued"
    case spawning = "Spawning Agents"
    case callingGemini = "Calling Gemini"
    case nativeScoring = "Invoking Native C++ Scoring"
    case complete = "Complete"
    case failed = "Needs Attention"

    var progress: Double {
        switch self {
        case .idle: return 0.0
        case .queued: return 0.12
        case .spawning: return 0.32
        case .callingGemini: return 0.62
        case .nativeScoring: return 0.86
        case .complete: return 1.0
        case .failed: return 1.0
        }
    }

    var symbol: String {
        switch self {
        case .idle: return "circle"
        case .queued: return "clock"
        case .spawning: return "person.3.sequence"
        case .callingGemini: return "network"
        case .nativeScoring: return "cpu"
        case .complete: return "checkmark.circle.fill"
        case .failed: return "exclamationmark.triangle.fill"
        }
    }
}

private final class EvolutionViewModel: ObservableObject {
    @Published var budget = "25000"
    @Published var location = "Austin, TX"
    @Published var targetSector = "AI tools for small businesses"
    @Published var generations = "3"
    @Published var seedCount = "4"

    @Published var stage: ProcessStage = .idle
    @Published var response: EvolutionResponse?
    @Published var diagnostics: [DiagnosticMessage] = [
        DiagnosticMessage(level: .info, message: "Gateway target: http://127.0.0.1:8080/evolve")
    ]
    @Published var isRunning = false

    var progress: Double { stage.progress }

    func generate() {
        guard !isRunning else { return }

        guard let request = makeRequest() else {
            stage = .failed
            diagnostics.insert(DiagnosticMessage(level: .error, message: "Check the form values. Budget, generations, and seed count must be numeric."), at: 0)
            return
        }

        isRunning = true
        response = nil
        diagnostics.insert(DiagnosticMessage(level: .info, message: "Queued request for \(request.targetSector) in \(request.location)."), at: 0)

        Task {
            await runGeneration(request)
        }
    }

    @MainActor
    private func runGeneration(_ request: EvolutionRequest) async {
        withAnimation(.easeInOut(duration: 0.2)) { stage = .queued }
        try? await Task.sleep(nanoseconds: 180_000_000)
        withAnimation(.easeInOut(duration: 0.2)) { stage = .spawning }
        try? await Task.sleep(nanoseconds: 240_000_000)
        withAnimation(.easeInOut(duration: 0.2)) { stage = .callingGemini }

        do {
            let result = try await EvolutionAPI.shared.evolve(request)
            withAnimation(.easeInOut(duration: 0.2)) { stage = .nativeScoring }
            try? await Task.sleep(nanoseconds: 280_000_000)
            response = result
            diagnostics.insert(DiagnosticMessage(level: .success, message: "Received \(result.successCount) ideas. Aggregate score: \(formatted(result.aggregateScore))."), at: 0)
            withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) { stage = .complete }
        } catch {
            diagnostics.insert(DiagnosticMessage(level: .error, message: readable(error)), at: 0)
            withAnimation(.easeInOut(duration: 0.2)) { stage = .failed }
        }

        isRunning = false
    }

    private func makeRequest() -> EvolutionRequest? {
        guard
            let budgetValue = Double(budget),
            let generationsValue = Int(generations),
            let seedValue = Int(seedCount),
            !location.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
            !targetSector.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else { return nil }

        return EvolutionRequest(
            budget: budgetValue,
            location: location,
            targetSector: targetSector,
            generations: generationsValue,
            seedCount: seedValue
        )
    }

    private func readable(_ error: Error) -> String {
        if let apiError = error as? EvolutionAPI.APIError {
            return apiError.message
        }
        if let urlError = error as? URLError {
            switch urlError.code {
            case .cannotConnectToHost, .networkConnectionLost, .notConnectedToInternet:
                return "Cannot reach the local Go gateway. Start it with make run."
            case .timedOut:
                return "The request timed out after 20 seconds. The gateway may still be waiting on Gemini."
            default:
                return "Network error: \(urlError.localizedDescription)"
            }
        }
        return error.localizedDescription
    }
}

private struct EvolutionRequest: Encodable {
    let budget: Double
    let location: String
    let targetSector: String
    let generations: Int
    let seedCount: Int

    enum CodingKeys: String, CodingKey {
        case budget
        case location
        case targetSector = "target_sector"
        case generations
        case seedCount = "seed_count"
    }
}

private struct EvolutionResponse: Decodable {
    let successCount: Int
    let errorCount: Int
    let ideas: [BusinessIdea]
    let errors: [String]?
    let aggregateScore: Double
    let averageFeasibilityScore: Double
    let returnedEarly: Bool?
    let elapsedMS: Int?

    enum CodingKeys: String, CodingKey {
        case successCount = "success_count"
        case errorCount = "error_count"
        case successfulWorkers = "successful_workers"
        case failedWorkers = "failed_workers"
        case ideas
        case errors
        case aggregateScore = "aggregate_score"
        case averageFeasibilityScore = "average_feasibility_score"
        case returnedEarly = "returned_early"
        case elapsedMS = "elapsed_ms"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        successCount = try container.decodeIfPresent(Int.self, forKey: .successCount)
            ?? container.decodeIfPresent(Int.self, forKey: .successfulWorkers)
            ?? 0
        errorCount = try container.decodeIfPresent(Int.self, forKey: .errorCount)
            ?? container.decodeIfPresent(Int.self, forKey: .failedWorkers)
            ?? 0
        ideas = try container.decodeIfPresent([BusinessIdea].self, forKey: .ideas) ?? []
        errors = try container.decodeIfPresent([String].self, forKey: .errors)
        aggregateScore = try container.decodeIfPresent(Double.self, forKey: .aggregateScore) ?? 0
        averageFeasibilityScore = try container.decodeIfPresent(Double.self, forKey: .averageFeasibilityScore) ?? 0
        returnedEarly = try container.decodeIfPresent(Bool.self, forKey: .returnedEarly)
        elapsedMS = try container.decodeIfPresent(Int.self, forKey: .elapsedMS)
    }
}

private struct BusinessIdea: Decodable, Identifiable {
    let id = UUID()
    let conceptName: String
    let estimatedStartupCost: Double
    let feasibilityScore: Double
    let riskFactors: [String]
    let marketingAngle: String

    enum CodingKeys: String, CodingKey {
        case conceptName = "concept_name"
        case estimatedStartupCost = "estimated_startup_cost"
        case feasibilityScore = "feasibility_score"
        case riskFactors = "risk_factors"
        case marketingAngle = "marketing_angle"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        conceptName = try container.decode(String.self, forKey: .conceptName)
        estimatedStartupCost = try container.decode(Double.self, forKey: .estimatedStartupCost)
        feasibilityScore = try container.decode(Double.self, forKey: .feasibilityScore)
        marketingAngle = try container.decode(String.self, forKey: .marketingAngle)
        if let risks = try? container.decode([String].self, forKey: .riskFactors) {
            riskFactors = risks
        } else if let risk = try? container.decode(String.self, forKey: .riskFactors) {
            riskFactors = [risk]
        } else {
            riskFactors = []
        }
    }
}

private struct DiagnosticMessage: Identifiable {
    enum Level {
        case info
        case success
        case error

        var tint: Color {
            switch self {
            case .info: return .accentColor
            case .success: return .green
            case .error: return .red
            }
        }
    }

    let id = UUID()
    let level: Level
    let message: String
}

private final class EvolutionAPI {
    enum APIError: Error {
        case badURL
        case nonHTTPResponse
        case server(status: Int, body: String)
        case decoding(message: String, raw: String)

        var message: String {
            switch self {
            case .badURL:
                return "Invalid local gateway URL."
            case .nonHTTPResponse:
                return "Gateway returned a non-HTTP response."
            case let .server(status, body):
                return "Gateway error \(status): \(body)"
            case let .decoding(message, raw):
                return "Could not decode gateway JSON: \(message). Raw: \(raw)"
            }
        }
    }

    static let shared = EvolutionAPI()

    private let endpoint = URL(string: "http://127.0.0.1:8080/evolve")
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    func evolve(_ request: EvolutionRequest) async throws -> EvolutionResponse {
        guard let endpoint else { throw APIError.badURL }

        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.timeoutInterval = 20
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.httpBody = try encoder.encode(request)

        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 20
        configuration.timeoutIntervalForResource = 20
        let session = URLSession(configuration: configuration)

        let (data, response) = try await session.data(for: urlRequest)
        guard let http = response as? HTTPURLResponse else { throw APIError.nonHTTPResponse }

        let raw = String(data: data, encoding: .utf8) ?? "<non-utf8 response>"
        print("Raw /evolve response:", raw)

        guard (200..<300).contains(http.statusCode) else {
            throw APIError.server(status: http.statusCode, body: raw)
        }

        do {
            return try decoder.decode(EvolutionResponse.self, from: data)
        } catch {
            throw APIError.decoding(message: error.localizedDescription, raw: String(raw.prefix(600)))
        }
    }
}

private struct SidebarView: View {
    @Binding var selectedSection: SidebarSection?
    @ObservedObject var viewModel: EvolutionViewModel

    var body: some View {
        List(SidebarSection.allCases, selection: $selectedSection) { section in
            Label(section.rawValue, systemImage: section.symbol)
                .font(.system(size: 13, weight: .medium))
                .tag(section)
                .padding(.vertical, 4)
        }
        .listStyle(.sidebar)
        .safeAreaInset(edge: .bottom) {
            VStack(alignment: .leading, spacing: 8) {
                StatusChip(stage: viewModel.stage)
                Text("Local Gateway")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("127.0.0.1:8080")
                    .font(.caption.monospaced())
                    .foregroundStyle(.secondary)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.regularMaterial)
        }
    }
}

private struct HeaderView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Idea Evolution Engine")
                .font(.system(size: 30, weight: .semibold, design: .rounded))
            Text("Generate, repair, rank, and inspect high-potential business concepts through the local Go and C++ pipeline.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
    }
}

private struct ParameterForm: View {
    @ObservedObject var viewModel: EvolutionViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Parameters")
                    .font(.title3.weight(.semibold))

                OutlinedField(title: "Budget", helper: "Initial capital in USD", text: $viewModel.budget)
                OutlinedField(title: "Location", helper: "City, region, or target geography", text: $viewModel.location)
                OutlinedField(title: "Target Sector", helper: "Market niche or customer segment", text: $viewModel.targetSector)

                HStack(spacing: 12) {
                    OutlinedField(title: "Generations", helper: "Evolution depth", text: $viewModel.generations)
                    OutlinedField(title: "Seeds", helper: "Starting pool", text: $viewModel.seedCount)
                }

                Button {
                    viewModel.generate()
                } label: {
                    Label(viewModel.isRunning ? "Generating" : "Generate Ideas", systemImage: viewModel.isRunning ? "hourglass" : "sparkles")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(viewModel.isRunning)
            }
            .padding(18)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .shadow(color: .black.opacity(0.08), radius: 12, x: 0, y: 5)
        }
        .frame(minHeight: 430)
    }
}

private struct OutlinedField: View {
    let title: String
    let helper: String
    @Binding var text: String
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(focused ? Color.accentColor : .secondary)
            TextField(title, text: $text)
                .textFieldStyle(.plain)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color(nsColor: .textBackgroundColor), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                .overlay {
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(focused ? Color.accentColor : Color.secondary.opacity(0.35), lineWidth: focused ? 1.5 : 1)
                }
                .focused($focused)
            Text(helper)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}

private struct ProgressTracker: View {
    let stage: ProcessStage
    let progress: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Execution")
                    .font(.title3.weight(.semibold))
                Spacer()
                StatusChip(stage: stage)
            }

            ProgressView(value: progress)
                .progressViewStyle(.linear)
                .tint(stage == .failed ? .red : .accentColor)
                .animation(.easeInOut(duration: 0.25), value: progress)

            HStack(spacing: 8) {
                ForEach(ProcessStage.allCases.filter { $0 != .idle && $0 != .failed }, id: \.rawValue) { item in
                    Circle()
                        .fill(item.progress <= progress ? Color.accentColor : Color.secondary.opacity(0.25))
                        .frame(width: 8, height: 8)
                }
                Spacer()
                Text("\(Int(progress * 100))%")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
        }
        .padding(18)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .shadow(color: .black.opacity(0.08), radius: 12, x: 0, y: 5)
    }
}

private struct StatusChip: View {
    let stage: ProcessStage

    var body: some View {
        Label(stage.rawValue, systemImage: stage.symbol)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(chipTint.opacity(0.14), in: Capsule())
            .foregroundStyle(chipTint)
    }

    private var chipTint: Color {
        switch stage {
        case .complete: return .green
        case .failed: return .red
        case .idle: return .secondary
        default: return .accentColor
        }
    }
}

private struct ScoreSummary: View {
    let response: EvolutionResponse?

    var body: some View {
        HStack(spacing: 12) {
            SummaryMetric(title: "Aggregate", value: formatted(response?.aggregateScore ?? 0), symbol: "sum")
            SummaryMetric(title: "Average", value: formatted(response?.averageFeasibilityScore ?? 0), symbol: "gauge.with.dots.needle.67percent")
            SummaryMetric(title: "Workers", value: "\(response?.successCount ?? 0)/\(max((response?.successCount ?? 0) + (response?.errorCount ?? 0), backendWorkerCount))", symbol: "person.3")
        }
    }
}

private struct SummaryMetric: View {
    let title: String
    let value: String
    let symbol: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(title, systemImage: symbol)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title3.monospacedDigit().weight(.semibold))
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .shadow(color: .black.opacity(0.07), radius: 10, x: 0, y: 4)
    }
}

private struct DiagnosticsPanel: View {
    let diagnostics: [DiagnosticMessage]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Diagnostics")
                .font(.headline)
            ForEach(diagnostics.prefix(4)) { item in
                HStack(alignment: .top, spacing: 8) {
                    Circle()
                        .fill(item.level.tint)
                        .frame(width: 7, height: 7)
                        .padding(.top, 5)
                    Text(item.message)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                    Spacer()
                }
            }
        }
        .padding(18)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .shadow(color: .black.opacity(0.08), radius: 12, x: 0, y: 5)
    }
}

private struct IdeasGrid: View {
    let ideas: [BusinessIdea]

    private let columns = [
        GridItem(.adaptive(minimum: 300, maximum: 430), spacing: 16, alignment: .top)
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Generated Concepts")
                .font(.title3.weight(.semibold))

            if ideas.isEmpty {
                EmptyIdeasView()
            } else {
                LazyVGrid(columns: columns, alignment: .leading, spacing: 16) {
                    ForEach(ideas) { idea in
                        IdeaCard(idea: idea)
                    }
                }
            }
        }
    }
}

private struct EmptyIdeasView: View {
    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "sparkle.magnifyingglass")
                .font(.system(size: 34))
                .foregroundStyle(.secondary)
            Text("Generated concepts will appear here.")
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 170)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.secondary.opacity(0.18), lineWidth: 1)
        }
    }
}

private struct IdeaCard: View {
    let idea: BusinessIdea

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                Text(idea.conceptName)
                    .font(.headline)
                    .lineLimit(2)
                Spacer()
                ScoreBadge(score: idea.feasibilityScore)
            }

            Text(idea.marketingAngle)
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            HStack {
                Label(currency(idea.estimatedStartupCost), systemImage: "banknote")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                Spacer()
                RiskBadge(count: idea.riskFactors.count)
            }

            Divider()

            VStack(alignment: .leading, spacing: 6) {
                Text("Risk Factors")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                ForEach(idea.riskFactors, id: \.self) { risk in
                    Text("• \(risk)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding(18)
        .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .stroke(Color.secondary.opacity(0.12), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.16), radius: 18, x: 0, y: 8)
    }
}

private struct ScoreBadge: View {
    let score: Double

    var body: some View {
        Text("\(Int(score))")
            .font(.caption.monospacedDigit().weight(.bold))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(tint.opacity(0.15), in: Capsule())
            .foregroundStyle(tint)
            .accessibilityLabel("Feasibility score \(Int(score))")
    }

    private var tint: Color {
        switch score {
        case 85...: return .green
        case 70..<85: return .orange
        default: return .red
        }
    }
}

private struct RiskBadge: View {
    let count: Int

    var body: some View {
        Label("\(count) risks", systemImage: "exclamationmark.shield")
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background(Color.orange.opacity(0.14), in: Capsule())
            .foregroundStyle(.orange)
    }
}

private func formatted(_ value: Double) -> String {
    value.formatted(.number.precision(.fractionLength(1)))
}

private func currency(_ value: Double) -> String {
    value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
}

#Preview {
    ContentView()
}
