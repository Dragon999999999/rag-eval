import { useState } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { SectionHeader } from "@/components/ui/section-header";
import { Card } from "@/components/layout/card";
import { Panel } from "@/components/layout/panel";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Radio } from "@/components/ui/radio";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Spinner } from "@/components/ui/spinner";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { MetricCard } from "@/components/ui/metric-card";
import {
  Search,
  MoreVertical,
  Info,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
} from "lucide-react";

export function DesignSystemShowcase() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectValue, setSelectValue] = useState("");

  return (
    <TooltipProvider>
      <div className="space-y-8 p-6">
        <PageHeader
          title="Design System"
          description="RAG-Eval UI component library and design tokens"
        />

        {/* Colors */}
        <section>
          <SectionHeader title="Colors" description="Semantic design tokens" />
          <Card className="space-y-4 p-4">
            <div>
              <h4 className="mb-2 text-sm font-medium text-text-secondary">
                Backgrounds
              </h4>
              <div className="grid grid-cols-5 gap-2">
                <div className="h-16 rounded-md border border-border-default bg-background" />
                <div className="h-16 rounded-md border border-border-default bg-surface" />
                <div className="h-16 rounded-md border border-border-default bg-surface-elevated" />
                <div className="h-16 rounded-md border border-border-default bg-surface-hover" />
                <div className="h-16 rounded-md border border-border-default bg-surface-active" />
              </div>
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium text-text-secondary">Accent</h4>
              <div className="grid grid-cols-4 gap-2">
                <div className="h-16 rounded-md bg-accent" />
                <div className="h-16 rounded-md bg-accent-hover" />
                <div className="h-16 rounded-md bg-accent-active" />
                <div className="h-16 rounded-md bg-accent-subtle" />
              </div>
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium text-text-secondary">Status</h4>
              <div className="grid grid-cols-4 gap-2">
                <div className="h-16 rounded-md bg-success-bg" />
                <div className="h-16 rounded-md bg-warning-bg" />
                <div className="h-16 rounded-md bg-error-bg" />
                <div className="h-16 rounded-md bg-info-bg" />
              </div>
            </div>
          </Card>
        </section>

        {/* Typography */}
        <section>
          <SectionHeader title="Typography" description="Text styles and hierarchy" />
          <Card className="space-y-4 p-4">
            <div>
              <h1 className="text-2xl font-semibold text-text-primary">Heading 1</h1>
              <h2 className="text-xl font-semibold text-text-primary">Heading 2</h2>
              <h3 className="text-base font-medium text-text-primary">Heading 3</h3>
              <p className="text-text-secondary">
                Body text - secondary color for primary content
              </p>
              <p className="text-sm text-text-tertiary">
                Small text - tertiary for descriptions
              </p>
              <p className="text-xs text-text-disabled">Extra small - disabled state</p>
            </div>
          </Card>
        </section>

        {/* Buttons */}
        <section>
          <SectionHeader title="Buttons" description="Action triggers" />
          <Card className="space-y-4 p-4">
            <div className="flex flex-wrap gap-2">
              <Button variant="primary">Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="danger">Danger</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm">Small</Button>
              <Button size="md">Medium</Button>
              <Button size="lg">Large</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button loading>Loading</Button>
              <Button disabled>Disabled</Button>
              <Button leftIcon={<Search />}>With Icon</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <IconButton icon={<Search />} variant="ghost" />
              <IconButton icon={<MoreVertical />} variant="secondary" />
              <IconButton icon={<Info />} size="sm" />
              <IconButton icon={<CheckCircle />} size="lg" />
            </div>
          </Card>
        </section>

        {/* Form Inputs */}
        <section>
          <SectionHeader title="Form Inputs" description="Data entry components" />
          <Card className="space-y-4 p-4">
            <Input label="Text Input" placeholder="Enter text..." />
            <Input label="With Error" error="This field is required" />
            <Input
              label="With Left Element"
              leftElement={<Search className="h-4 w-4" />}
            />
            <Textarea label="Textarea" placeholder="Enter description..." />
            <div className="flex gap-4">
              <Checkbox label="Checkbox option" />
              <Radio value="radio1" label="Radio option" />
              <Switch label="Switch toggle" />
            </div>
            <Select value={selectValue} onValueChange={setSelectValue}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="option1">Option 1</SelectItem>
                <SelectItem value="option2">Option 2</SelectItem>
                <SelectItem value="option3">Option 3</SelectItem>
              </SelectContent>
            </Select>
          </Card>
        </section>

        {/* Badges */}
        <section>
          <SectionHeader
            title="Badges"
            description="Status and categorization labels"
          />
          <Card className="space-y-4 p-4">
            <div className="flex flex-wrap gap-2">
              <Badge>Default</Badge>
              <Badge variant="primary">Primary</Badge>
              <Badge variant="success">Success</Badge>
              <Badge variant="warning">Warning</Badge>
              <Badge variant="error">Error</Badge>
              <Badge variant="info">Info</Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge status="success">Success</StatusBadge>
              <StatusBadge status="warning">Warning</StatusBadge>
              <StatusBadge status="error">Error</StatusBadge>
              <StatusBadge status="info">Info</StatusBadge>
              <StatusBadge status="neutral">Neutral</StatusBadge>
            </div>
          </Card>
        </section>

        {/* Table */}
        <section>
          <SectionHeader title="Table" description="Data display" />
          <Card className="p-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell>John Doe</TableCell>
                  <TableCell>
                    <StatusBadge status="success">Active</StatusBadge>
                  </TableCell>
                  <TableCell>Admin</TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem>Edit</DropdownMenuItem>
                        <DropdownMenuItem>Delete</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Jane Smith</TableCell>
                  <TableCell>
                    <StatusBadge status="warning">Pending</StatusBadge>
                  </TableCell>
                  <TableCell>User</TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem>Edit</DropdownMenuItem>
                        <DropdownMenuItem>Delete</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </Card>
        </section>

        {/* Tabs */}
        <section>
          <SectionHeader title="Tabs" description="Content organization" />
          <Card className="p-4">
            <Tabs defaultValue="tab1" className="w-full">
              <TabsList>
                <TabsTrigger value="tab1">Tab 1</TabsTrigger>
                <TabsTrigger value="tab2">Tab 2</TabsTrigger>
                <TabsTrigger value="tab3">Tab 3</TabsTrigger>
              </TabsList>
              <TabsContent value="tab1" className="mt-4">
                <p className="text-text-secondary">Content for tab 1</p>
              </TabsContent>
              <TabsContent value="tab2" className="mt-4">
                <p className="text-text-secondary">Content for tab 2</p>
              </TabsContent>
              <TabsContent value="tab3" className="mt-4">
                <p className="text-text-secondary">Content for tab 3</p>
              </TabsContent>
            </Tabs>
          </Card>
        </section>

        {/* Dialog */}
        <section>
          <SectionHeader title="Dialog" description="Modal overlays" />
          <Card className="p-4">
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button>Open Dialog</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Dialog Title</DialogTitle>
                  <DialogDescription>
                    This is a dialog description. It provides context for the action.
                  </DialogDescription>
                </DialogHeader>
                <div className="py-4">
                  <p className="text-sm text-text-secondary">
                    Dialog content goes here. You can put any content you need.
                  </p>
                </div>
                <DialogFooter>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setDialogOpen(false);
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      setDialogOpen(false);
                    }}
                  >
                    Confirm
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </Card>
        </section>

        {/* Tooltip & Popover */}
        <section>
          <SectionHeader
            title="Tooltip & Popover"
            description="Additional information"
          />
          <Card className="space-y-4 p-4">
            <div className="flex gap-4">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="secondary">Hover for tooltip</Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>This is a tooltip</p>
                </TooltipContent>
              </Tooltip>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="secondary">Click for popover</Button>
                </PopoverTrigger>
                <PopoverContent>
                  <p className="text-sm">This is a popover with more content</p>
                </PopoverContent>
              </Popover>
            </div>
          </Card>
        </section>

        {/* Progress & Loading */}
        <section>
          <SectionHeader title="Progress & Loading" description="Feedback indicators" />
          <Card className="space-y-4 p-4">
            <div className="space-y-2">
              <ProgressBar value={25} />
              <ProgressBar value={50} />
              <ProgressBar value={75} />
              <ProgressBar value={100} />
            </div>
            <div className="flex items-center gap-4">
              <Spinner size="sm" />
              <Spinner size="md" />
              <Spinner size="lg" />
            </div>
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </Card>
        </section>

        {/* Empty State */}
        <section>
          <SectionHeader title="Empty State" description="No content states" />
          <Card className="p-4">
            <EmptyState
              icon={<Info className="h-8 w-8" />}
              title="No results found"
              description="Try adjusting your search or filter criteria"
              action={<Button size="sm">Clear filters</Button>}
            />
          </Card>
        </section>

        {/* Alerts */}
        <section>
          <SectionHeader title="Alerts" description="Status messages" />
          <Card className="space-y-4 p-4">
            <Alert>
              <AlertTitle>Default Alert</AlertTitle>
              <AlertDescription>
                This is a default alert message with additional description.
              </AlertDescription>
            </Alert>
            <Alert variant="success">
              <CheckCircle className="h-4 w-4" />
              <AlertTitle>Success</AlertTitle>
              <AlertDescription>Operation completed successfully.</AlertDescription>
            </Alert>
            <Alert variant="warning">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Warning</AlertTitle>
              <AlertDescription>Please review before continuing.</AlertDescription>
            </Alert>
            <Alert variant="error">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>
                Something went wrong. Please try again.
              </AlertDescription>
            </Alert>
          </Card>
        </section>

        {/* Metric Cards */}
        <section>
          <SectionHeader title="Metric Cards" description="Key metrics display" />
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Total Runs"
              value="1,234"
              trend={{ value: "+12%", direction: "up" }}
              description="Last 30 days"
            />
            <MetricCard
              label="Success Rate"
              value="98.5%"
              trend={{ value: "+2.1%", direction: "up" }}
              description="Average"
            />
            <MetricCard
              label="Avg. Latency"
              value="245ms"
              trend={{ value: "-15ms", direction: "down" }}
              description="Target: <300ms"
            />
            <MetricCard
              label="Failed Cases"
              value="23"
              trend={{ value: "+5", direction: "down" }}
              description="Requires attention"
            />
            <MetricCard
              label="Loading State"
              value="---"
              loading
              description="Fetching data..."
            />
          </div>
        </section>

        {/* Panels */}
        <section>
          <SectionHeader title="Panels" description="Content containers with headers" />
          <Card className="p-4">
            <Panel title="Panel Title" action={<Button size="sm">Action</Button>}>
              <p className="text-sm text-text-secondary">
                Panel content goes here. Panels provide a structured way to organize
                related content with an optional header and actions.
              </p>
            </Panel>
          </Card>
        </section>
      </div>
    </TooltipProvider>
  );
}
