"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/api-client";
import { CheckIcon, XIcon, PencilIcon } from "lucide-react";

interface ProposalActionsProps {
  proposalId: string;
  currentNewValue: string;
  onActionComplete?: () => void;
}

export function ProposalActions({
  proposalId,
  currentNewValue,
  onActionComplete,
}: ProposalActionsProps) {
  const [rejectReason, setRejectReason] = useState("");
  const [editValue, setEditValue] = useState(currentNewValue);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  async function handleApprove() {
    setLoading(true);
    setMessage(null);
    try {
      await apiClient.approveProposal(proposalId);
      setMessage({ type: "success", text: "Proposal approved successfully." });
      onActionComplete?.();
    } catch {
      setMessage({ type: "error", text: "Failed to approve proposal." });
    } finally {
      setLoading(false);
    }
  }

  async function handleReject() {
    setLoading(true);
    setMessage(null);
    try {
      await apiClient.rejectProposal(proposalId, rejectReason);
      setMessage({ type: "success", text: "Proposal rejected." });
      setRejectOpen(false);
      setRejectReason("");
      onActionComplete?.();
    } catch {
      setMessage({ type: "error", text: "Failed to reject proposal." });
    } finally {
      setLoading(false);
    }
  }

  async function handleEdit() {
    setLoading(true);
    setMessage(null);
    try {
      await apiClient.editProposal(proposalId, editValue);
      setMessage({ type: "success", text: "Proposal edited successfully." });
      setEditOpen(false);
      onActionComplete?.();
    } catch {
      setMessage({ type: "error", text: "Failed to edit proposal." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      {message && (
        <div
          className={`rounded-lg px-4 py-2 text-sm ${
            message.type === "success"
              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
              : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-2">
        {/* Approve */}
        <AlertDialog>
          <AlertDialogTrigger
            data-testid="approve-btn"
            disabled={loading}
            render={<Button className="w-full md:w-auto bg-green-600 text-white hover:bg-green-700" />}
          >
            <CheckIcon className="size-4" />
            Approve
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Apply this change?</AlertDialogTitle>
              <AlertDialogDescription>
                This will approve the proposed change and apply it to the live
                data. This action cannot be easily undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleApprove}
                className="bg-green-600 text-white hover:bg-green-700"
              >
                Confirm Approve
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Reject */}
        <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
          <DialogTrigger
            data-testid="reject-btn"
            disabled={loading}
            render={<Button variant="destructive" className="w-full md:w-auto" />}
          >
            <XIcon className="size-4" />
            Reject
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Reject Proposal</DialogTitle>
            </DialogHeader>
            <div className="space-y-2">
              <label htmlFor="reject-reason" className="text-sm font-medium">
                Reason (required)
              </label>
              <Textarea
                id="reject-reason"
                placeholder="Explain why this change should be rejected..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button
                variant="destructive"
                disabled={!rejectReason.trim() || loading}
                onClick={handleReject}
              >
                Submit Rejection
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit */}
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogTrigger
            data-testid="edit-btn"
            disabled={loading}
            render={<Button variant="outline" className="w-full md:w-auto" />}
          >
            <PencilIcon className="size-4" />
            Edit
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Proposed Value</DialogTitle>
            </DialogHeader>
            <div className="space-y-2">
              <label htmlFor="edit-value" className="text-sm font-medium">
                New value
              </label>
              <Textarea
                id="edit-value"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button disabled={loading} onClick={handleEdit}>
                Save Edit
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
